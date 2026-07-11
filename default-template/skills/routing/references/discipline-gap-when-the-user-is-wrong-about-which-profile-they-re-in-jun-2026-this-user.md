## Discipline gap: when the user is wrong about which profile they're in (Jun 2026, this user)

Distinct from the trigger-matched-but-not-emitted gap above: the user sometimes starts a session in `default` because that's where they ended up, not because they chose it. The trigger list matches a specialised profile (joandrew → communicate-design, etc.) but the user is unaware of the profile-router. The fix is to surface the router suggestion **at the start of the session** if the user's first message matches a non-default profile's triggers — not wait for the first wrong-action. The session-ritual already does some of this; the router adds the explicit one-line suggestion:

> "This looks like communicate-design work. You're in default right now. Two paths: (a) open a new tab with `hermes -p communicate-design chat` to use the right context, (b) say 'stay in default' and I'll do it here. Or (c) I can dispatch a subagent with communicate-design's persona — fastest path if you want this done in this session."

The (c) option is the underused one. Most users don't want to context-switch; they want the work done. The subagent-dispatch is the right default for class-of-work that crosses profile boundaries.
