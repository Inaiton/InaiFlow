# Design reference
`screens/*.dc.html` are the approved Claude Design canvas screens (one file per screen, prefix = module:
Acc- Accounts, Ops- Operations, Doc- Documents, Org- Organization, Me-/Auth-/Onb- personal & onboarding,
SA- superadmin, Glb- global overlays, Sidebar/Topbar/AccBar/RBar shell components).
They are static HTML mockups (custom `<x-dc>` markup with inline styles) — use them for layout, copy,
hierarchy and colours; implement with the web app's own components. `design_lib_reference.py` holds the
palette and component vocabulary used to generate them.
Live canvas: https://claude.ai/artifact/E2zLaGqvCpvMR4r12mXPoF
