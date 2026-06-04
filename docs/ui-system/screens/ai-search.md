# Screen — AI Search

**Purpose.** Natural-language entry returning a grounded answer above ranked instruments.

## Layout
Prominent input (⌘K overlay). AI answer card (answer+confidence+sources) above ranked result list.

## Components
- SearchInput
- AIAnswerCard
- ResultList

## API requirements
- `POST /v1/ai/search (quota-gated)`
- `GET /v1/instruments/search`

## Data model (entities)
- ai_conversations
- ai_messages
- vector store (retrieval)

## Loading states
Answer block shows shimmer lines; results stream after.

## Error states
AI unavailable → friendly error, raw search results still shown; quota hit → upgrade prompt.

## Responsive rules
Full-width overlay; mobile hides ⌘K hint.

## Analytics events
- `ai_search`
- `ai_answer_view`
- `ai_result_click`
- `ai_quota_hit`
