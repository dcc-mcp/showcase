from dcc_mcp_core.skill import skill_entry, skill_success
from .common import audit
@skill_entry
def main():
    return skill_success('Live REAPER session audited', **audit())
