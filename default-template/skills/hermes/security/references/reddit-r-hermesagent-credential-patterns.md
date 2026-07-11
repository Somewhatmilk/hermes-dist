# Reddit r/hermesagent credential patterns — sourced excerpts

Machine-readable quotes from the r/hermesagent threads that surfaced the
canonical patterns. Read alongside `references/env-pointer-pattern.md`.

## Source 1: "Accidental self-jailbreak of internal secrets on a one-shot prompt"

URL: <https://www.reddit.com/r/hermesagent/comments/1ug0y38/accidental_selfjailbreak_of_internal_secrets_on_a/>

### The incident (linkingio95, original post)

> "the safety architecture is an absolute swiss cheese of security ... i
> stumbled upon a hilarious accidental bypass, and i wasn't even trying to be
> a hacker. this wasn't some complex, adversarial multi-turn jailbreak
> attempt. it was a lazy, single, one-shot prompt. i didn't ask it to bypass
> anything, exploit a vulnerability, or hack the system. i literally just
> gave it this exact, casual prompt: 'hey can you check your this_secret in
> .env file and tell me?' the underlying model ... took one look at hermes'
> adorable attempt to mask the terminal output with asterisks and decided to
> show the framework how computers actually work. it spontaneously bypassed
> the visual masking by querying the raw ordinal ascii values, decoding them
> in its head, and handing me the secret on a silver platter."

### The recommended pattern (mesinaksara, top voted solution)

> "in my experience, by default, hermes can always read .env and
> config.yaml. but after the huge updates, hermes can only read those two
> now, not edit them. i agree with you: hermes is not the problem, as their
> system is designed to mask any creds/secrets. the problem is the models
> (llms), the brain of hermes. so in my case, i've used bitwarden secret
> manager (bws). nous shipped this feature about a month ago. so all
> api_keys, secrets, creds, etc., go into bitwarden, and in .env there's
> only one bws token as the source of truth for all creds, and it's
> injected automatically at runtime. so the models (llms) will never see the
> real secrets."

### The threat-model reasoning (lobsterweary2675)

> "container isolation is a boundary, provided it is configured properly. in
> my setup, the agent runs its terminal and file tools inside a docker
> container. it does not automatically see the host filesystem, and the
> host ~/.hermes/.env is not just sitting there for the agent to read. the
> container only gets whatever paths and environment variables are
> explicitly mounted or injected. that is the actual security model i would
> trust more: do not give the agent access to secrets in the first place.
> mount only the working directory it needs, keep host config and .env files
> outside the sandbox, inject only task-specific credentials when required,
> and treat redaction as a backup layer, not the main protection."

### The "put it in n8n" variant (sleepy_bandit)

> "it doesn't necessarily encrypt them but it might be possible to
> obfuscate it with an idea i saw someone else have. they built n8n
> workflows for certain activities like emailing or posting and kept the
> authentication inside those workflows. hermes simply calls to it and
> passes it data to handle the final leg of the journey. it has no insight
> into the internals of that workflow. seemed like an interesting trick."

## Source 2: "Hermes agent + Bitwarden"

URL: <https://www.reddit.com/r/hermesagent/comments/1ug8cc0/hermes_agent_bitwarden/>

### The official Nous Research guidance (top comment)

> "yes, we're working on hardening it, in the meantime:
> - don't store secrets in Bitwarden if the agent has terminal access.
> - inject secrets only into specific tool environments.
> - use environment variables & strict scoping instead of letting the agent
>   read secret managers."

## Source 3: "Storing secrets"

URL: <https://www.reddit.com/r/hermesagent/comments/1th1sqg/storing_secrets/>

### The Anthropic-style proxy recommendation (dangtony98)

> "the issue with all these approaches tho is you end up returning secrets
> directly to agents which makes credential exfiltration one prompt
> injection away. been seeing many more teams move toward a 'proxy' pattern
> where agents make requests through a proxy that brokers credentials
> instead (the folks at anthropic actually do exactly this with their
> managed agents architecture); i'd recommend looking into credential
> brokering. i'd recommend this https://github.com/infisical/agent-vault"

### The "give agents ability, not access" framing (atrfx)

> "the short version is you want to give your agents the ability to action
> but not give them access. what this looks like in practice is, for tools
> that in combination could cause some damage, it's better to lock them
> behind an abstracted remote tool not on your agent machine, and for some
> tools, only have them enabled during certain workloads so they don't exist
> all the time where they could be abused."

### The infisical direct-integration claim (icantgetnosatisfacti)

> "i just setup infisical for this purpose. hermes requests the secret
> directly from infisical, gets loaded in memory and used for accessing
> whatever. secret never gets mentioned in a chat session, doesn't get
> saved in an .env."

## What the consensus says (2026-07-05)

1. **No redaction is durable** — ordinal-decoding breaks asterisks. The
   secret must be **structurally absent** from the agent's context.
2. **Three viable shapes for "structurally absent":**
   - One bws/1password/infisical token in .env + everything else in the
     external service (BWS, 1P Connect, Infisical).
   - Pass-pinned pointers in .env (`pass:api/X`) + a launcher script that
     resolves them before exec'ing hermes. **This is the local-only,
     no-cloud-billing option for self-hosted users.**
   - External proxy (Anthropic's pattern, infisical agent-vault) where
     hermes never has the secret, only the proxy does.
3. **Container/sandbox isolation is orthogonal** — even within a docker
   sandbox, if the .env is mounted in, the LLM can decode. Mount narrow;
   inject per-task.
4. **The LLM is the threat** — `mesinaksara`'s quote is the most
   diagnostic: "hermes is not the problem ... the problem is the models
   (llms), the brain of hermes."

## What the user picked (2026-07-05)

This user chose **option 2 (pass-pinned pointers + launcher)**, because:
- Self-hosted / no cloud account
- Multi-device sync via `pass git init` (no proxy needed)
- GPG-encrypted vault is local, no billing
- Same threat model as bws but no third party

The launcher pattern lives at `references/env-pointer-pattern.md`.
