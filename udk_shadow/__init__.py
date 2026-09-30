"""Phase 6B: shadow mode. Runs Phase 3 (udk_context) + Phase 4 evidence (udk_signals) + Phase 5 (udk_fusion)
beside the live path, per udk_fusion/PHASE6_INTEGRATION_CONTRACT.md, and records what they would have
decided. The live path stays authoritative: shadow never changes, delays or suppresses a live alert and
never mutates live state. OFF unless UDK_SHADOW_MODE=1. Architecture and schema: udk_shadow/README.md.
"""
