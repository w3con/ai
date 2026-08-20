---
description: Use whenever Alex asks about his mail in any wording — "проверь почту", "прочти почту", "посмотри почту", "почитай почту", "что нового в почте", "есть ли новые письма", "check the mail", "read my mail", "what came in", "/read-mail" — or asks what has arrived, or names a correspondent and asks what they wrote. Scans both self-hosted mailboxes for messages that have not been looked at yet, reads the ones that matter, and stages a reply for each into the drafts page of the Validité knowledge base.
allowed-tools: Bash, Read, Edit, Write, Grep, Glob
---

You are checking Alexander's business mail and staging replies for him to send by hand.

**Arguments:** `$ARGUMENTS` — optional. A mailbox name (`validite` or `pilier`), a sender's name, or `--all` to ignore the record of what was already handled. With no arguments, scan both mailboxes for what is new.

## Rules that hold for the whole run

Never send, reply, forward or delete anything. The mail client is configured without an outgoing backend and must stay that way. Your output is a draft on a page, and Alexander sends it himself.

Call the mail client only as `~/.local/bin/himalaya` (or through `read-mail-scan`, which resolves it for you). Never call `himalaya.real`. Every call waits at least fifteen seconds, so read only the messages you actually need, and never retry a failed call: repeated failures get this machine's address banned by the mail host.

Bash calls that touch the mail need `dangerouslyDisableSandbox: true`.

## 1. Scan

```
~/Dev/ai/bin/read-mail-scan
```

It lists only what has not been shown before, in both mailboxes. Pass `--accounts validite`, `--size 40` or `--all` when the argument asks for it. If it reports exit code 75, the throttle is refusing: read what it says, wait, and do not work around it.

If it reports no local client, stop and say so, naming the mail section of the Validité `CLAUDE.md` as the fix. Do not improvise a different path to the mailbox.

## 2. Triage before reading

From the subject and sender alone, sort the new messages into three groups and read only the third:

- **Noise** — newsletters, digests, automatic out-of-office replies, invoices from suppliers, platform notifications. Name them in one line each in your report and read none of them.
- **For information** — a real person writing something that needs no answer. Read it only if the subject is ambiguous.
- **Needs a reply** — a person asking a question, proposing a meeting, making an introduction, or waiting on something Validité owes them.

```
~/.local/bin/himalaya message read <ID> -a <account> -f INBOX
```

## 3. Get the context before drafting

For every message that needs a reply, before writing a word:

- Find the contact's card: start at `kb/_index.md`, then read the card under `kb/BizDev/contacts/`. It carries the history, what was promised, what is still open, and what the last letter did wrong.
- Read the existing drafts page, `kb/BizDev/_drafts.md`, in full. It carries the standing rules for letters and may already hold a staged draft for this same person.
- Check the calendar with `list_events` before proposing or accepting any date.
- Correct anything the card says was factually wrong in an earlier letter. Do not repeat a mistake because the thread contains it.

## 4. Write the drafts

Add one `##` section per letter to `kb/BizDev/_drafts.md`, placed above the `## Deferred` section, following the shape the page already uses:

- A heading naming the person, the organisation and what the letter does.
- Short prose saying which thread it replies into, which address, and every decision you took that Alexander might want to reverse.
- The letter under the bold label `**Текст письма (копировать отсюда):**`, as plain paragraphs.
- A French letter is followed by a horizontal rule and a Russian translation, marked as being for review only.

Letters obey these without exception: reply inside the existing thread, never a new subject; match the language the thread already uses; no `>` blockquote markers anywhere in the body; no em-dashes; and no emotional cushioning in a French letter — no permission to refuse, no reassurance about pressure, no menu of options. State the thing and stop.

Leave a fact missing and say it is missing rather than inventing a date, a figure or a name.

Do not run `ai/bin/kb-reflow` on the drafts page.

## 5. Close the run

Record what you handled so the next scan does not show it again:

```
~/Dev/ai/bin/read-mail-scan --mark-seen
```

Update each contact's card whose message you drafted a reply to: the `next_touch` field and the open action list. Do not change `last_touch`, which records a send, and nothing has been sent.

Then report to Alexander in chat: what arrived, what you ignored and why, what you drafted, and every decision inside a draft that he may want to reverse. Show the letter text in chat as well, so he can read it without opening the page.
