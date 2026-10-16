# Selected-answer quiz review

This supersedes the answer-key review described in employee-feedback-verification.md.

After submitting all questions, employees review results inline on the quiz page. Only their selected option is green (correct) or red (incorrect); alternative options remain neutral. Answer keys and explanations are never sent by learner grading or course APIs, including passing attempts. Saved passing selections receive correctness flags for that selection only. Historical missing answers do not receive invented results.

The server continues to calculate score and pass status. Continue advances explicitly; Finish course handles the final module. Failed attempts retain review until Rewatch lesson, then follow the existing video replay requirement. Course resume and Trainer draft-notification expiry are unchanged.

Validation: 18 backend grading, payload-disclosure and progress-persistence tests; 18 focused Employee widget, result-parser, resume and playback-guard tests; JavaScript release build; focused static analysis; compiled Chrome acceptance covering 2/3, 3/3, failed review, saved selections, resume, duplicate options and mobile layout.

Deploy backend and Employee frontend together. Preserve the Trainer image and deployment environment. No schema, grade or learner-progress migration is required. Failed selected answers remain session-only under the existing persistence policy.
