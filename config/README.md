# Configure public job boards

The APIs below expose public job postings per company; they do not provide a global index of all employers.

1. Open a company's careers page.
2. Identify the ATS from the URL:
   - Greenhouse: `boards.greenhouse.io/<board>` or `job-boards.greenhouse.io/<board>`
   - Lever: `jobs.lever.co/<site>`
   - Ashby: `jobs.ashbyhq.com/<board>`
3. Add the company and exact board/site slug to `boards.json`.
4. Set `enabled` to `true`.
5. Run `python run_discovery.py` to test.

Use only public postings and modest request rates. A successful HTTP response does not mean the posting is suitable for a 2027 fresher; Gemini analysis in Phase 3 will inspect actual requirements.

The starter config intentionally contains disabled placeholders rather than guessed company slugs. The target of 100 is a maximum number of matched postings to process per run, not a guarantee that 100 new eligible jobs exist.
