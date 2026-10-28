---
name: check-numbers
description: "Quick check of a paper with Plumb: its tables, statistics, and arithmetic, whether the numbers in the text match the tables, whether each work in its reference list exists with matching authors and year, and whether the tool read the paper right. No full review. Use when the user asks to check the numbers, stars, p-values, or references in a paper."
---

Invoke the plumb `review` skill for the given PDF. At Quick depth it checks the tables, the statistics, the arithmetic, and whether the numbers in the text match the tables. It looks up each work in the paper's reference list. Then it shows a short summary of how it read the paper and asks you to confirm it. It does not check quotes or claims in a review draft, which run only at Standard or Deep depth. At setup, pre-fill Depth: Quick and check-in level: Standard, and ask only the remaining setup and consent questions, in Stage 0's order. The consent gate still runs before anything reads the PDF.
