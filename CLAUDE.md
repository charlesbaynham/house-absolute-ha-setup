# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Documentation Location

**All architectural documentation, conventions, and development guidelines are maintained in:**

`.github/copilot-instructions.md`

This file serves as the single source of truth for both GitHub Copilot and Claude Code to avoid duplication and ensure consistency.

Please read that file for:
- Project architecture and structure
- Configuration patterns and conventions
- Entity ID types and usage
- TRV PID controller setup
- Common tasks and examples
- Troubleshooting guidance

## Claude Code Specific Notes

When working with this Home Assistant configuration repository:

- This is YAML configuration only - there are no build, test, or compile commands
- Use `yamllint *.yaml packages/*.yaml` to validate YAML syntax locally (note: full validation requires Home Assistant restart due to custom tags like `!include` and `!secret`)
- Changes take effect after Home Assistant service restart (not done from this repository)
- When searching for existing patterns or understanding features, check the `packages/` directory first as related config is grouped there
