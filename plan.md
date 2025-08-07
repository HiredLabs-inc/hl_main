# Plan to Accomplish Weekly Review Objectives

## 1. Refactor Data Access from JSON to Database
- **Goal:** Eliminate reliance on .json files for job data and retrieve all necessary information directly from the database.
- **Steps:**
  1. Locate the code in `views.py` (specifically in `JobDetailView`, around line 341) where job data is currently accessed or should be accessed.
  2. Identify all places where job data is loaded from JSON files in the codebase.
  3. Refactor those sections to instead query the database for job information after a job description is added and analysis is performed.
  4. Ensure the refactored code uses the database as the single source of truth for job data.

## 2. Pass Data from DB into Keyword Analysis
- **Goal:** Ensure data retrieved from the database is passed into the `analyze` function in `keyword_analyzer.py`.
- **Steps:**
  1. Review the `analyze` function in `keyword_analyzer.py` to understand its input requirements and supported keyword categories (such as `nltk_stopwords`, `low_value`, `industry_protected`).
  2. Update the data flow in `views.py` so that data fetched from the database is formatted and passed into `analyze`.
  3. Ensure the system can handle analyzing one or more categories at a time, and that this is configurable as needed.

## 3. Testing Plan
- **Goal:** Validate that the refactored system works as intended and that keyword analysis is robust.
- **Steps:**
  1. Test the integration between the DB retrieval and the `analyze` function for all supported keyword categories.
  2. Experiment with different stopword parameters and ensure the system behaves as expected.
  3. Create algorithmic tests using known inputs and expected outputs to confirm correct analysis behavior.
  4. Document all tests performed, including:
      - What was tested
      - Why the test was performed
      - How the test was conducted
      - The results and any insights

## 4. Documentation
- **Goal:** Ensure all work is well-documented for future reference.
- **Steps:**
  1. Clearly document the refactoring process, including what was changed and why.
  2. Record the details of all tests and their outcomes.
  3. Maintain up-to-date comments and docstrings in the codebase.

## Summary Table
| Step | Description                                  | File(s) Involved                |
|------|----------------------------------------------|---------------------------------|
| 1    | Refactor data access from JSON to DB         | views.py, any JSON-read scripts |
| 2    | Pass DB data into `analyze`                  | views.py, keyword_analyzer.py   |
| 3    | Test integration and analysis functionality  | tests/, views.py, keyword_analyzer.py |
| 4    | Document changes and results                 | plan.md, code comments, docs/   |

---

**Current Focus:** Refactor to retrieve and process data from the DB, then ensure robust keyword analysis and thorough testing/documentation.
