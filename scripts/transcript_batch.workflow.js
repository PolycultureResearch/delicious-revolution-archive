export const meta = {
  name: 'transcript-batch',
  description: 'Lightly edit, structure and speaker-label a batch of Delicious Revolution episode transcripts',
  phases: [{ title: 'Edit and format', detail: 'one agent per episode' }],
}

// args: { ids: ["<episode_id>", ...] }
const ROOT = '/Users/devon/Documents/code/delicious-revolution-archive'
const REPORT = {
  type: 'object',
  properties: {
    episode_id: { type: 'string' },
    words_whisper: { type: 'number' },
    words_edited: { type: 'number' },
    words_formatted: { type: 'number' },
    speakers: { type: 'string', description: 'speakers found, with turn counts' },
    low_confidence_turns: { type: 'number' },
    problems: { type: 'string', description: 'anything that stopped the work or needs a human; empty if none' },
  },
  required: ['episode_id', 'words_whisper', 'words_edited', 'words_formatted', 'speakers', 'low_confidence_turns', 'problems'],
}

const prompt = id => `Turn one machine podcast transcript into an edited, structured, speaker-labelled transcript. This is careful copy-editing, not summarizing.

Repo: ${ROOT} (use absolute paths; do not use git; write only the three output files named below).
Episode id: ${id}

Read first:
- ${ROOT}/transcripts/INSTRUCTIONS.md (the rules; follow them exactly)
- ${ROOT}/transcripts/names.md (correct spellings of hosts and every guest on the show)
- this episode's row in ${ROOT}/data/episodes.csv (columns title, notes_text; read with Python's csv module)
- input: ${ROOT}/transcripts/whisper/${id}.txt

Do the steps in order, overwriting any existing output:
1. Step 2 of the instructions: write ${ROOT}/transcripts/edited/${id}.md. Work through the input in order in chunks of about 100 lines, writing the output incrementally, and cover it to the last line.
2. Step 3 of the instructions: write ${ROOT}/transcripts/formatted/${id}.md from the edited file. Apart from the removals the instructions call for, the wording must match the edited file.
3. Write the report described in the instructions' "Report" section to ${ROOT}/transcripts/reports/${id}.md, as markdown with a "# <episode title>" heading and one "## " section per report item. Quote removed boilerplate and sponsorship text exactly.

Count words with wc -w. Then return the structured summary.`

const ids = args.ids
log(`${ids.length} episodes in this batch`)
const results = await parallel(ids.map(id => () =>
  agent(prompt(id), { label: id.slice(11, 45), phase: 'Edit and format', schema: REPORT })))
const failed = ids.filter((id, i) => !results[i])
if (failed.length) log(`no result for: ${failed.join(', ')}`)
return { done: results.filter(Boolean), failed }
