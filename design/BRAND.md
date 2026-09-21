# Workshop brand

The look of the two documents every teaching repository prints: the **attendee workbook** and
the **facilitator guide**. It is the colours of clickhouse.com, sampled on 2026-09-19. The values
live in `workshop-tokens.json`; this file says what they are for and what never to do with them.

This is a palette, not a claim. A repository that uses it is not a ClickHouse product unless it is one.

## Colour

Near-white paper, near-black ink, and one loud yellow used sparingly.

| Name | Value | For |
|---|---|---|
| paper | `#FAFAFA` | the page |
| card | `#FFFFFF` | a raised block: a diagram, a table |
| ink | `#151515` | body text and headings |
| ink-2 | `#414141` | the opening line of a chapter |
| muted | `#606060` | captions, notes, labels |
| faint | `#808080` | figure numbers, large or bold only |
| line | `#DFDFDF` | hairlines, box outlines |
| accent | `#FAFF69` | **a fill, with ink on top.** The one marked box in a diagram, a highlight bar |
| accent-deep | `#4F5101` | text or a rule that has to be yellow-toned on paper |
| fill-dark | `#1F1F1C` | the one dark box in a diagram, command blocks on screen |
| pass / fail / wait | `#008138` `#BF000F` `#B75000` | it worked, it was refused, it is waiting on a person |

Rules:

1. **Yellow is never text on paper.** It is 1.03 to 1 against the page. Put ink on top of yellow, or use accent-deep.
2. **One dark box and one yellow box per diagram.** That is the whole budget for emphasis. Two of either means neither is the point.
3. **Green, red and amber mean what they say** and nothing else. Do not use red because a box is important.
4. **Diagrams name a colour, they never write a hex.** `scripts/diagram.mjs` reads the names from the tokens.
5. **Light only.** No dark mode, no toggle.

## Type

- **Inter** for headings and body. No serif anywhere. **Inconsolata** for commands, file names and identifiers.
- Söhne and Basier, the faces clickhouse.com itself uses, are licensed and are not shipped.
- Weight stops at 700 and letter spacing stays normal in print. A heavier weight, or wide or negative tracking, prints fine and
  then extracts as gibberish, which the PDF read-back catches.

## The page

A4, one column, 174 mm of print width. Heading, picture, caption and text share one left edge, and a picture spans the column.
Body text is 11.5pt, about 78 characters a line. A note that says why an idea matters is a callout under the text, not a side column.

## The pictures

Every diagram is drawn by `scripts/diagram.mjs` on a canvas 504 units wide. The page is 504 points of print width, so a unit prints as
about a point. Type sizes are 11 (title), 9.5 (label) and 8.5 (note). Nothing draws below 8.

## Words

Plain English. If a word needs a glossary, use a shorter one. Do not name a thing after how the system is built.
