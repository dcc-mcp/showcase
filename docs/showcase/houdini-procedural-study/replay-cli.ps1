param(
 [Parameter(Mandatory=$true)][string]$InstanceId,
 [Parameter(Mandatory=$true)][string]$CaseDirectory,
 [string]$SessionId='houdini-procedural-study-replay',
 [string]$BaseUrl,
 [switch]$Render
)
$ErrorActionPreference='Stop'
$recipe=Get-Content -LiteralPath (Join-Path $PSScriptRoot 'recipe.json') -Raw | ConvertFrom-Json
$resolvedCase=[System.IO.Path]::GetFullPath($CaseDirectory).Replace('\','/')
New-Item -ItemType Directory -Path $resolvedCase -Force | Out-Null
$logDirectory=Join-Path $resolvedCase '.mcp-replay-private-logs'
New-Item -ItemType Directory -Path $logDirectory -Force | Out-Null
$common=@('--require-gateway','--agent-session-id',$SessionId,'--output','json')
if ($BaseUrl) { $common+=@('--base-url',$BaseUrl) }
$script:callIndex=0
function Invoke-CLI([string[]]$CommandArguments) {
 $text=(& dcc-mcp-cli @CommandArguments @common | Out-String)
 if ($LASTEXITCODE -ne 0) { throw "dcc-mcp-cli exited $LASTEXITCODE" }
 return ($text | ConvertFrom-Json)
}
function Invoke-Typed([string]$Tool,[object]$Payload) {
 $inventory=Invoke-CLI @('search','--query',$Tool,'--dcc-type','houdini','--instance-id',$InstanceId,'--limit','4')
 $matches=@($inventory.hits | Where-Object { $_.tool_slug.EndsWith(".$Tool") })
 if ($matches.Count -ne 1) { throw "Exact scoped typed tool unavailable: $Tool" }
 $hit=$matches[0]
 if (-not $hit.loaded) {
  $skill=$hit.next_step.arguments.skill_name
  if (-not $skill) { throw "Missing advertised load-skill step for $Tool" }
  Invoke-CLI @('load-skill',$skill,'--instance-id',$InstanceId,'--activate-groups','true') | Out-Null
 }
 $script:callIndex++
 $inputFile=Join-Path $logDirectory "$($script:callIndex)-arguments.json"
 $Payload | ConvertTo-Json -Depth 30 | Set-Content -LiteralPath $inputFile -Encoding utf8
 $response=Invoke-CLI @('call',$hit.tool_slug,'--json-file',$inputFile,'--wait','--wait-timeout-secs','600')
 $response | ConvertTo-Json -Depth 40 | Set-Content -LiteralPath (Join-Path $logDirectory "$($script:callIndex)-response.json") -Encoding utf8
 $output=$response.output
 if ($response.structuredContent.result) { $output=$response.structuredContent.result }
 if (-not $output -or $output.success -isnot [bool] -or $output.success -ne $true) { throw "Typed call failed or omitted an explicit success flag: $Tool" }
 return $output
}
# Operator must select a newly bootstrapped, test-owned instance from inventory.
Invoke-CLI @('list') | Out-Null
$initial=Invoke-Typed 'houdini_scene__get_scene_info' @{}
$count=$initial.context.obj_node_count
$hasFile=$initial.context.hip_has_file
$isNumeric=($count -is [byte] -or $count -is [sbyte] -or $count -is [int16] -or $count -is [uint16] -or $count -is [int32] -or $count -is [uint32] -or $count -is [int64] -or $count -is [uint64] -or $count -is [decimal] -or $count -is [double] -or $count -is [single])
if (-not $isNumeric -or $count -ne 0 -or $hasFile -isnot [bool] -or $hasFile -ne $false) {
 throw 'Replay requires a dedicated empty unsaved scene; existing scene was left untouched.'
}
foreach ($step in $recipe.steps) {
 if ($step.tool -eq 'houdini_render__render_rop' -and -not $Render) { continue }
 $payloadText=($step.arguments | ConvertTo-Json -Depth 30 -Compress).Replace('CASE_DIR',$resolvedCase)
 $output=Invoke-Typed $step.tool ($payloadText | ConvertFrom-Json)
 if ($step.tool -eq 'houdini_render__render_rop') {
  $job=$output.context.job_id
  if (-not $job) { throw 'Render did not return its adapter-owned job ID.' }
  $deadline=(Get-Date).AddMinutes(10)
  do {
   Start-Sleep -Seconds 2
   $status=Invoke-Typed 'houdini_render__get_render_job' @{job_id=$job;include_details=$true}
   if ((Get-Date) -gt $deadline) { throw 'Render polling deadline reached; inspect the existing job, do not resubmit.' }
  } while ($status.context.state -notin @('completed','failed','cancelled'))
  if ($status.context.state -ne 'completed' -or $status.context.output_verification.state -ne 'verified') {
   throw 'Render outputs did not pass adapter verification.'
  }
 }
 Write-Output "Completed $($step.tool)"
}
Invoke-Typed 'houdini_geometry__get_geometry_info' @{node_path='/obj/showcase_20261001_ceramic/OUT_ceramic'} | ConvertTo-Json -Depth 10
Write-Output 'Replay completed. Raw logs and ordinary HIP saves retain local metadata; audit before publishing.'
