# React frontend decisions

Visual thesis: a quiet ivory document workspace with ink typography and one indigo accent, built for reading source evidence.

Content plan: persistent bid navigation; search, questions and extraction in the primary workspace; source details in a secondary inspector; indexing available from the selected bid.

Interaction thesis: short workspace entrance; result selection opens an evidence inspector; tabs and loading states transition subtly. Respect reduced-motion preferences.

- React, TypeScript and Vite provide a small typed frontend with a fast development server.
- Proxy /api to FastAPI to avoid broad CORS permissions.
- Discover bids through the API so unseen folders appear without frontend changes.
- Keep search separate from generation: search works without LLM credentials.
- Display evidence as plain text to avoid executing document markup.
- Load existing extraction records and export JSON rather than inventing sample answers.
- Cancel stale browser requests when changing scope; server work can continue after cancellation.
- Use document typography rather than stock photography for this operational tool.
- Use Lucide action icons and CSS motion; avoid a heavy component framework.

The original bonus-UI deferral is superseded by the user's explicit frontend request.

- Keyboard tabs use arrow/Home/End navigation; the folder dialog traps Tab and supports Escape, so core workflows remain usable without a mouse.
- Keep generated records in the backend output directory and expose read-only loading through the API to share CLI and UI results.
- Ignore frontend build/dependency directories and commit the npm lockfile for reproducible installation.
- Responsive navigation and a stacked evidence inspector keep document reading usable on small screens.

Validation: production TypeScript/Vite build passed; 24 Python tests passed. Browser verification used real Bid1 retrieval, source inspection, provider configuration errors, dialog dismissal, and 390px mobile overflow checks. Generated answer/record rendering and exports require a live provider or a saved record and were not exercised with live generated data.

## Monochrome refresh
Visual thesis: white workspace, neutral gray context, black primary actions and modern Inter typography.
Content plan: retain bid navigation and search/question/extraction workspaces with evidence beside results.
Interaction thesis: retain quick tab/inspector transitions and focus affordances with reduced-motion support.
Reasons: black is the requested primary color; neutral grays organize surfaces without competing accents. Inter and system sans-serif fallbacks give consistent modern typography across headings and source passages. Smaller semibold headings, clearer body text, thin dividers and removed search shadows simplify the reading hierarchy.
