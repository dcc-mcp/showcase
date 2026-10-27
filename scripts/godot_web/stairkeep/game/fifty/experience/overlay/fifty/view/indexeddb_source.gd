extends RefCounted
## Original slot envelopes stay opaque here; FiftySave validates their identity,
## checksums and runtime semantics before a compare-and-swap or state import.
## Transaction completion plus readback is not a physical power-loss guarantee.

const SCRIPT := """
(function () {
    'use strict';
    const root = globalThis;
    if (root.StairkeepChapterOneStorageV1) {
        return;
    }
    const DB_NAME = 'stairkeep-chapter-one-storage-v1';
    const STORE = 'slots';
    const MAX_BYTES = 8388608;
    const TIMEOUT_MS = 30000;
    const KEY = /^stairkeep-fifty-slice[/]v1[/](classic_restart|practice_checkpoint)[/][a-z0-9][a-z0-9_-]{0,31}$/;
    const RESERVED = new Set(['con', 'prn', 'aux', 'nul', 'com1', 'com2', 'com3', 'com4', 'com5', 'com6', 'com7', 'com8', 'com9', 'lpt1', 'lpt2', 'lpt3', 'lpt4', 'lpt5', 'lpt6', 'lpt7', 'lpt8', 'lpt9']);

    function validKey(key) {
        if (typeof key !== 'string') return false;
        const match = key.match(KEY);
        return match !== null && match[0] === key && !RESERVED.has(key.slice(key.lastIndexOf('/') + 1));
    }

    function validText(text, Encoder) {
        return typeof text === 'string' && text.length > 0 && text.length <= MAX_BYTES && new Encoder().encode(text).length <= MAX_BYTES;
    }

    function validRecord(value, Encoder) {
        return value !== null && typeof value === 'object' && !Array.isArray(value) &&
            Object.keys(value).sort().join(',') === 'schema,text' && value.schema === 1 && validText(value.text, Encoder);
    }

    function run(key, expected, text, callback, writing) {
        let done = false;
        let db = null;
        let tx = null;
        let writeIssued = false;
        let committed = false;
        let durability = 'unknown';
        let timer = null;
        let factory = null;
        let Encoder = null;

        function finish(result) {
            if (done) return;
            done = true;
            try {
                if (timer !== null) clearTimeout(timer);
                if (db !== null) {
                    db.onversionchange = null;
                    db.close();
                }
            } catch (closeError) {
                // Closing a connection cannot invalidate a completed transaction.
            } finally {
                // Never fire synchronously: the Godot caller installs its await next.
                setTimeout(function () { callback(JSON.stringify(result)); }, 0);
            }
        }

        function fail(status, error, uncertain) {
            const result = {ok: false, status: status, uncertain: !!uncertain};
            if (error && typeof error.name === 'string') result.error_name = error.name;
            finish(result);
        }

        function stop(status, error) {
            let uncertain = committed;
            if (tx !== null) {
                try { tx.abort(); }
                catch (abortError) { uncertain = uncertain || writeIssued; }
            }
            fail(uncertain ? 'web_commit_unconfirmed' : status, error, uncertain);
        }

        timer = setTimeout(function () { stop('web_timeout', null); }, TIMEOUT_MS);
        if (typeof callback !== 'function') {
            if (timer !== null) clearTimeout(timer);
            done = true;
            return;
        }
        try {
            factory = root.indexedDB;
            Encoder = root.TextEncoder;
            if (!factory || typeof factory.open !== 'function' || typeof Encoder !== 'function') {
                fail('web_storage_unavailable', null, false);
                return;
            }
            if (!validKey(key) || (writing && ((expected !== null && !validText(expected, Encoder)) || !validText(text, Encoder)))) {
                fail('web_invalid_request', null, false);
                return;
            }
        } catch (error) { fail('web_storage_unavailable', error, false); return; }

        function readback() {
            let value;
            let gotValue = false;
            try {
                tx = db.transaction([STORE], 'readonly');
                const request = tx.objectStore(STORE).get(key);
                request.onsuccess = function () { value = request.result; gotValue = true; };
                tx.onerror = function () { /* onabort owns the terminal result. */ };
                tx.onabort = function () { fail('web_commit_unconfirmed', tx.error, true); };
                tx.oncomplete = function () {
                    if (done) return;
                    if (!gotValue || !validRecord(value, Encoder) || value.text !== text) {
                        fail('web_commit_unconfirmed', null, true);
                        return;
                    }
                    finish({ok: true, status: 'saved_web', uncertain: false, durability: durability});
                };
            } catch (error) { fail('web_commit_unconfirmed', error, true); }
        }

        function transact() {
            let value;
            let gotValue = false;
            let refusal = null;
            try {
                if (writing) {
                    try { tx = db.transaction([STORE], 'readwrite', {durability: 'strict'}); }
                    catch (error) {
                        if (error.name !== 'TypeError' && error.name !== 'NotSupportedError') throw error;
                        tx = db.transaction([STORE], 'readwrite');
                    }
                    if (typeof tx.durability === 'string') durability = tx.durability;
                } else tx = db.transaction([STORE], 'readonly');
                const store = tx.objectStore(STORE);
                const request = store.get(key);
                request.onsuccess = function () {
                    try {
                        if (done) return;
                        value = request.result;
                        gotValue = true;
                        if (value !== undefined && !validRecord(value, Encoder)) {
                            refusal = 'web_invalid_record';
                            if (writing) tx.abort();
                            return;
                        }
                        if (!writing) return;
                        const actual = value === undefined ? null : value.text;
                        if (actual !== expected) {
                            refusal = 'web_conflict';
                            tx.abort();
                            return;
                        }
                        const record = {schema: 1, text: text};
                        // add also refuses an unexpected first-write collision.
                        if (expected === null) store.add(record, key);
                        else store.put(record, key);
                        writeIssued = true;
                    } catch (error) { stop('web_transaction_failed', error); }
                };
                tx.onerror = function () { /* Error requests abort by default; wait for it. */ };
                tx.onabort = function () {
                    fail(refusal || 'web_transaction_aborted', tx.error, false);
                };
                tx.oncomplete = function () {
                    if (done) return;
                    if (!gotValue) { fail('web_read_failed', null, false); return; }
                    if (refusal !== null) { fail(refusal, null, false); return; }
                    if (writing) {
                        if (!writeIssued) { fail('web_write_failed', null, false); return; }
                        committed = true;
                        readback();
                    } else if (value === undefined) finish({ok: true, status: 'not_found', uncertain: false});
                    else finish({ok: true, status: 'read', text: value.text, uncertain: false});
                };
            } catch (error) { stop('web_transaction_failed', error); }
        }

        try {
            const request = factory.open(DB_NAME, 1);
            request.onblocked = function () { fail('web_open_blocked', null, false); };
            request.onerror = function () { fail('web_open_failed', request.error, false); };
            request.onupgradeneeded = function (event) {
                if (done) { event.target.transaction.abort(); return; }
                const opened = event.target.result;
                if (!opened.objectStoreNames.contains(STORE)) opened.createObjectStore(STORE);
            };
            request.onsuccess = function () {
                if (done) { request.result.close(); return; }
                db = request.result;
                db.onversionchange = function () { stop('web_storage_changed', null); };
                if (!db.objectStoreNames.contains(STORE)) { fail('web_invalid_database', null, false); return; }
                transact();
            };
        } catch (error) { fail('web_open_failed', error, false); }
    }

    root.StairkeepChapterOneStorageV1 = Object.freeze({
        contract: 1,
        read_slot: function (key, callback) { run(key, null, null, callback, false); },
        commit_slot: function (key, expected, text, callback) { run(key, expected, text, callback, true); }
    });
}());
"""
