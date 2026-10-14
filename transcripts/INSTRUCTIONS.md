# How the transcripts are made

Each published episode goes through three steps. Files are named by `episode_id`.

1. `whisper/<id>.txt|vtt|json`: machine transcript from `scripts/transcribe.sh` (verbatim, no speakers).
2. `edited/<id>.md`: light edit, plain paragraphs.
3. `formatted/<id>.md`: structure and speaker labels. This is the version for the site.

Spelling authorities, in order: the episode's `title` and `notes_text` in `data/episodes.csv`,
then `transcripts/names.md`, then general knowledge (allowed, but every such fix is reported).

## Step 2: light edit

- Keep every substantive thing that was said, in the speaker's own words and order. Do not
  summarize, paraphrase, condense, reorder, or improve phrasing or grammar. Expect the output
  to be roughly 85 to 99 percent of the input word count.
- Remove fillers (um, uh, filler "like", "you know", "I mean", "sort of" and "kind of" when pure
  filler), stutters and immediate repetitions, and abandoned false starts where the speaker
  restarts the sentence. Backchannel interjections that only acknowledge another speaker
  ("Yeah.", "Right.", "Mm-hmm.") can go. Drop Whisper artifacts such as a stray "you" or "Bye."
  at the very end.
- Fix names of people, organizations, farms, places, foods and non-English terms. Fix a
  mishearing only when the intended word is clear from context. If unsure, leave Whisper's text.
- Fix punctuation and capitalization. Join caption lines into paragraphs: a new paragraph at each
  apparent change of speaker, and long single-speaker stretches split every few sentences.
- No speaker labels or headings in this step. No em dashes: use commas, colons or new sentences.

## Step 3: structure and speaker labels

The audio usually runs: teaser quote from the guest, introduction to the show, introduction of the
guest, interview, closing. Parts can be missing or in a different order. Output shape:

    > *Teaser quote in italics.*
    >
    > Guest Full Name

    ## Introduction

    **Host Full Name:** introduction of the guest and episode

    ## Interview

    **Host Full Name:** question

    **Guest Full Name:** first paragraph of the answer

    later paragraphs of the same turn carry no label

    ## Closing

    **Host Full Name:** announcements and credits

- Teaser only if the episode opens with a guest quote; attribute it to whoever says it.
- Remove, wherever they occur (opening, closing, or mid-episode):
  - the generic introduction to the show ("Welcome to Delicious Revolution, a show about food,
    culture, and place. I'm ... This season we're ... You can subscribe ...");
  - generic "you are listening to", subscribe, website and social media lines;
  - sponsorship messages and ad reads (often a pre-roll before or after the teaser).
- Keep everything specific to the episode or guest, all announcements (events, newsletters,
  upcoming episodes), and all credits: who made the show, thanks, and funder acknowledgements
  such as "made possible with support from California Humanities". When unsure whether a line
  is a sponsorship message or a funder credit, keep it and report it.
- Omit a heading if that part does not exist. Short items with no interview (announcements,
  specials) use only the headings that fit.
- Label every turn with the speaker's full name in bold and a colon. Merge adjacent paragraphs
  of one speaker into a single turn; split a paragraph that clearly holds two speakers.
- Infer speakers from the text only: introductions, who asks questions, first-person facts, forms
  of address, continuity. Always give a best guess.
- Apart from the removals above, do not change the wording of the edited text.

## Report

For each episode, report: word counts (whisper, edited, formatted); name and term corrections
from the notes; corrections from general knowledge or context; names left uncertain; passages
left garbled; the exact text of removed boilerplate and sponsorship messages; hosts and
speakers found with turn counts; and low-confidence speaker attributions.
