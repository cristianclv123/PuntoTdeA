# Consumption guide: WhatsApp webhook (Meta Cloud API)

Audience: campaign team and chatbot team. This is a handoff document; it describes
what already exists and where each team plugs in.

> **First, the most important clarification:** you don't consume the HTTP endpoint.
> **Meta** calls it, once, from the outside. Your team doesn't make requests to the
> webhook. What you consume is the code on either side of it.

```
                        ┌──────────────────────┐
  Campaign team ───────▶│  send_campaign()     │──▶ Graph API ──▶ WhatsApp
                        └──────────────────────┘
                                                                       │
                          ┌──────────────────────┐                   │
  Meta ──POST /webhook──▶│  meta_webhook        │◀── status events ──┘
                          └──────────┬───────────┘
                     ┌─────────────┴─────────────┐
                     ▼                           ▼
        status → BroadcastRecipient      message → chatbot.handle_message
                                                   │
        Campaign team ◀── read state ─────────────┘
                    Bot team
```

Everything is a single endpoint, and it is already wired. **Nobody should create a
second webhook, re-validate the signature, or call Graph API directly.**

---

## 1. The endpoint

Canonical URL, the only one to register in Meta Developers:

```
POST https://TU-DOMINIO/api/whatsapp/webhook/
```

`/base-de-conocimiento/chatbot/whatsapp/` is an alias that calls the same function.
It exists so the old URL keeps working; **don't register it in Meta.**

### `GET` — subscription verification

Meta calls it once when you save the callback. It requires
`?hub.mode=subscribe&hub.verify_token=<token>&hub.challenge=<value>` and responds
with `hub.challenge` in plain text. If the token doesn't match `META_VERIFY_TOKEN`
it answers `403 Verification failed`.

### `POST` — events

| Condition | Response |
| --- | --- |
| Valid signature | `200 {"ok": true, "processed": N, "duplicates": N, "ignored": N, "unmatched": N}` |
| Missing/invalid `X-Hub-Signature-256` | `403 Invalid signature` |
| `META_APP_SECRET` not set | `403` always, no exceptions |
| Body isn't a JSON object | `400` |
| Unhandled exception while processing | `500 {"error": "No fue posible procesar el evento."}` |
| Method other than GET/POST | `405` |

The signature is `sha256=HMAC_SHA256(META_APP_SECRET, raw_body)`. **It is already
validated before any of your code runs.** Don't validate it again.

A `500` is deliberate: it's what makes Meta retry the event. Returning `200` on a
failure would drop it silently. See the retry caveat in section 6.

### How a payload gets routed

The payload nests as `entry[].changes[].value`, and inside that:

- `value.messages[]` → **inbound**, goes to the bot.
- `value.statuses[]` → **campaign status**, updates `BroadcastRecipient`.

Both branches are handled in the same request. An inbound message is discarded
before reaching the bot if it has no `id` or no `from`, if its `phone_number_id`
isn't the configured one, if `type != "text"`, or if the body is empty.

---

## 2. Campaign team

### What you call to send

```python
from communications.services.campaign_service import send_campaign

send_campaign(campaign)          # uses MetaAdapter
send_campaign(campaign, adapter) # only for tests
```

`send_campaign` is synchronous and lives in-process. Current entry points:

- `POST /api/campaigns/{id}/send/` (only from `draft` or `scheduled`)
- The send action in `/admin/communications/campaign/`

What it does, per recipient whose status is `pending`:

| Situation | Result |
| --- | --- |
| Contact has `whatsapp_opt_in = baja` | Status `opted_out`, no call to Meta |
| Meta accepts | Status `sent`, `provider='meta'`, `provider_message_id` = `wamid`, `sent_at` set, `ContactEvent` `message_sent` |
| Meta rejects or the call fails | Status `failed`, `error_message` filled with Meta's message, `ContactEvent` `message_failed` |

The campaign goes `sending` → `sent`. One HTTP call to Meta per recipient, with a
10 s timeout each, inside the request. **For a large audience this blocks: moving
scheduling and execution to a worker is your task, not this layer's.** Calling
`send_campaign` from a Celery task or a management command is all that's needed;
don't reimplement the per-recipient loop.

### Requirements for a message to actually go out

`MessageTemplate` must satisfy all of these, or `send_template_message` returns
`success=False` before any network call:

1. `status = approved` — the local flag, which someone has to set.
2. `meta_template_name` matches a template **that actually exists and is approved
   in the Meta account**, with the same name. Local approval isn't enough.
3. `language` matches the code registered in Meta (default `es_CO`).
4. Every `{{n}}` placeholder in `body_text` has a value in `params`. They're sent
   in ascending index order.
5. If `header_type != none`, `header_media_url` is set.

Phones are normalized to digits only (`+57 300 123 4567` → `573001234567`).

### What you get back for free: delivery states

You don't need to consume the webhook. The same endpoint that feeds the bot also
applies statuses to your `BroadcastRecipient`, matching on
`provider_message_id == wamid`. The `wamid` is saved at send time precisely so
this works, so **never write to `provider_message_id` by hand**.

| Meta status | Effect on `BroadcastRecipient` | Also sets |
| --- | --- | --- |
| `sent` | `sent` | `sent_at` |
| `delivered` | `delivered` | `delivered_at` |
| `read` | `read` | `read_at` |
| `failed` | `failed` + `error_message` | — |

Guarantees you can rely on:

- **No regressions.** A `delivered` that arrives after a `read` doesn't undo it.
  Progression is `pending(0) < queued(1) < sent(2) < delivered(3) < read(4)`.
- **`failed` only applies if the recipient isn't already `read`.** A failure
  arriving after a read is ignored.
- Each transition writes a `ContactEvent`, so `contact.events` has the history
  with `provider_message_id` in the payload.
- Every event is recorded in `WhatsAppWebhookEvent` whether or not it matched
  anything.

So your dashboard metrics (`delivered_count`, `read_count`, `failed_count`) already
read from these fields and need no change.

### When a status doesn't match

If the `wamid` doesn't match any recipient, the event is stored, logged as
"Estado de Meta sin destinatario de campaña", counted as `unmatched` and nothing
is modified. It's the diagnostic for "the `wamid` we saved isn't the one Meta is
reporting". Look at the events table in **WhatsApp (Meta) → Prueba de integración**,
or `/admin/communications/whatsappwebhookevent/`.

### How to test without spending money

```powershell
docker compose exec -T web python manage.py seed_demo_whatsapp
```

Creates 8 contacts, 2 segments and 2 campaigns. One campaign has a recipient
pre-seeded in every delivery state, so you can see metrics without sending
anything. The other is in `draft`, ready for a real send. The `wamid`s are
synthetic (`wamid.SEED…` prefix); clean up with `--limpiar`.

---

## 3. Bot team

### The seam you hook into

```python
from knowledge.chatbot import whatsapp as chatbot_whatsapp

replies = chatbot_whatsapp.handle_message(sender, text)   # -> list[str]
```

That's the whole contract. The webhook already extracted `sender` (the `from`
field) and `text` (the body), already filtered non-text messages, and it sends
each string in the returned list for you via `send_text`. You never see the
payload, the signature, or the HTTP layer.

`handle_message` is idempotent at the event level, not at the function level:
the webhook de-duplicates by `wamid` before calling it.

### Identity

`sender` is the raw `from` from Meta: digits only, no `+`. It is used as-is for
`ChatConversation.external_user_id` (`channel='whatsapp'`) and as the reply
address. **The phone number is the only identifier: there's no mapping table
from WhatsApp to `Contact`.** If you need to tie a conversation to a `Contact`,
you'll have to resolve it by phone, and that resolution isn't written yet.

### The state machine

`flow_state` on the conversation:

| State | What the bot does with the next message |
| --- | --- |
| `waiting_question` | Treats it as the question, answers, → `waiting_confirmation` |
| `waiting_confirmation` | `sí`/`s`/`yes` → `help_options`. `no`/`n` → `ended` (status `ended`). **Anything else re-asks and doesn't advance** |
| `help_options` | Contains `asesor`, `humano` or `persona` → escalates → `waiting_advisor_question`. Otherwise treated as a new question |
| `waiting_advisor_question` | Stores the request, status `pending` → `pending` |
| `ended` / `pending` | Fixed "already closed" reply |

Unknown state: starts over and submits the text as a question.

### Two behaviors that will confuse you if nobody tells you

**1. The first message's text is discarded.** On a new conversation,
`handle_message` returns the greeting and never looks at the text:

```python
if created or not conversation.messages:
    return [workflow.start()['message']]
```

So the first thing a person sends has to be a greeting; the question is only
processed from the second message onward. If you test by hand and the bot seems
to ignore you, this is why.

**2. In `waiting_confirmation` only yes/no works.** Anything else gets
"Respóndeme sí o no: ¿te puedo ayudar en algo más?" and **the message isn't
stored** in the conversation history.

### Persisted state

`ChatConversation`: `flow_state`, `status` (`active`/`ended`/`pending`),
`last_question`, `advisor_question`, `escalation_reason`, `escalated_at`, and
`messages` as a JSON list of `{author, content, created_at}`.
Visible in `/admin/knowledge/chatconversation/`.

### Extending it

- **Answers:** `generate_response(question, responder)`, where `responder` is
  `Callable[[str], dict]`. `ChatbotWorkflow` accepts `responder=` and
  `schedule=`, so a different implementation (an LLM, say) can be injected
  without touching the state machine.
- **Validation:** `validate_question(question) -> (bool, str)`. An invalid
  question re-asks and doesn't change state.
- **Schedule:** `schedule.is_open(current_time)` decides the closing message.
  Outside business hours the escalation says the request is pending instead of
  promising an advisor.

### Two behaviors that are correct, not bugs

- With an empty knowledge base the bot answers "No encontré información
  suficiente…". Load content with
  `docker compose exec -T web python manage.py seed_knowledge`.
- Outside business hours the closing message changes. Both are the designed
  behavior.

### How to test the whole conversation without a phone

**WhatsApp (Meta) → Prueba de integración → Simular webhook**, scenario
**"Guion completo del bot"**. It sends the five turns as five independent,
correctly signed webhooks through the real endpoint, so the state machine
actually advances. **Requires `META_APP_SECRET`**: with no secret there's no
signature and the webhook answers `403`. And since the bot answers the number you
type, a fake number means the reply never reaches a real phone — that's expected.

---

## 4. What both teams must not do

- Don't create a second webhook or a parallel route. There's one.
- Don't re-validate the signature. It's done, and it's mandatory.
- Don't call Graph API directly. Go through `MetaAdapter` or `chatbot_whatsapp.send_text`.
  A direct call skips `provider_message_id`, and the delivery states stop working.
- Don't assume a message you sent was delivered. `sent` only means Meta accepted it.
  Read receipts are what confirm delivery, and a read may never arrive.

## 5. Current limitations

Worth knowing before you design around them:

- **Only `type: "text"` inbound messages are processed.** Images, audio, documents
  and interactive replies (list messages, quick-reply buttons) are logged and
  discarded. If you need them, that's new work in `_process_inbound`.
- **`send_campaign` is synchronous.** Fine for tens of recipients, wrong for
  thousands. The async move is the campaigns team's.
- **A retried event can replay the bot's reply.** If `handle_message` succeeds but
  `send_text` then fails, the request returns `500`, Meta retries, and the bot
  answers again. The event is left unprocessed on purpose so it isn't lost, which
  means the trade-off is currently "at least once" rather than "exactly once". If
  duplicate replies become a problem, the fix is to record the outbound `wamid`
  per inbound event.
- **`META_APP_ID` is optional** and unused by the code. It doesn't block anything.
- Twilio and mock adapters still exist in the tree but aren't wired: the webhook
  is Meta only, and mock is only used by tests. Don't build on them.

## 6. Diagnosing a problem

```powershell
# Configuration and connectivity, exits 1 if something's missing
docker compose exec -T web python manage.py check_meta_whatsapp
docker compose exec -T web python manage.py check_meta_whatsapp --validate

# Event trail
docker compose exec -T web python manage.py shell -c "from communications.models import WhatsAppWebhookEvent as E; [print(e.created_at, e.event_type, e.status, e.provider_message_id, bool(e.processed_at)) for e in E.objects.all()[:20]]"
```

| Symptom | Cause |
| --- | --- |
| `403 Invalid signature` on every event | `META_APP_SECRET` empty or wrong, or the container wasn't recreated after editing `.env` |
| `Verification failed` | `META_VERIFY_TOKEN` in Meta ≠ `.env` |
| Events arrive, no state changes | The `wamid` doesn't match `provider_message_id`. Look for `unmatched` |
| Bot answers, nothing on the phone | The number in the simulator isn't a real one, or the wrong Phone Number ID |
| Bot answers twice | A retried event; see the limitation in section 5 |
| Campaign send fails immediately | Template not `approved`, or `meta_template_name` doesn't exist in the Meta account |

Remember `docker compose up -d --force-recreate web` after changing `.env`: a
`restart` keeps the old environment variables and will look like the config never
took effect.

Full reference: [`whatsapp-meta.md`](whatsapp-meta.md).
