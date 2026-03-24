❯ ccfm --config tests/smoke/ccfm-smoke.yaml apply --file "tests/smoke/docs/example/CCFM Example/complete_example.md"
Looking up space: CCFMDEV
   Space ID: 524292

ccfm will perform the following actions:

+ tests/smoke/docs/example/CCFM Example/complete_example.md (add)        "CCFM Example Files - Complete Element Reference"

Plan: 1 to add.

Do you want to apply these changes? Only 'yes' will be accepted: yes
   📄 Ensuring page: example (placeholder)
   ✨ Creating page: example
   📄 Ensuring page: CCFM Example (placeholder)
   ✨ Creating page: CCFM Example

📄 Processing: complete_example.md
   Title: CCFM Example Files - Complete Element Reference
   Status: current
   ⚠️  Warning: Page not found for link: CCFM Example - My Team
   ⚠️  Warning: Page not found for link: CCFM Example - My App
   ⚠️  Warning: Page not found for link: CCFM Example - My Team
   ✨ Creating new page
   👤 Author: Platform Team
   🏷️  Labels: ccfm, reference, example, author-platform-team, managed-by-ci
   📎 Uploading: CCFM.png
   🔑 Fetching Media Services fileId...
   ✓ Attachment ready: CCFM.png
   🔗 Resolving attachment media nodes...
   ✓ Page updated with 1 attachment(s)
   ✅ Success! Page ID: 32112641
   ℹ Attachment already exists (ID: att13140117), updating...

Apply complete!
❯ ccfm --config tests/smoke/ccfm-smoke.yaml apply --file "tests/smoke/docs/example/CCFM Example/My App/my_app.md"
Looking up space: CCFMDEV
   Space ID: 524292

ccfm will perform the following actions:

+ tests/smoke/docs/example/CCFM Example/My App/my_app.md (add)        "CCFM Example - My App"

Plan: 1 to add.

Do you want to apply these changes? Only 'yes' will be accepted: yes
   📄 Ensuring page: example (placeholder)
   ✓ Page 'example' exists (ID: 32047105)
   📄 Ensuring page: CCFM Example (placeholder)
   ✓ Page 'CCFM Example' exists (ID: 32079873)
   📄 Ensuring page: My App (placeholder)
   ✨ Creating page: My App

📄 Processing: my_app.md
   Title: CCFM Example - My App
   Status: current
   ✨ Creating new page
   👤 Author: CCFM Example Files
   🏷️  Labels: ccfm, reference, example, author-ccfm-example-files, managed-by-ci
   ✅ Success! Page ID: 32145419
   ℹ Attachment already exists (ID: att13140117), updating...

Apply complete!
❯ ccfm --config tests/smoke/ccfm-smoke.yaml apply --file "tests/smoke/docs/example/CCFM Example/My Team/my_team.md"
Looking up space: CCFMDEV
   Space ID: 524292

ccfm will perform the following actions:

+ tests/smoke/docs/example/CCFM Example/My Team/my_team.md (add)        "CCFM Example - My Team"

Plan: 1 to add.

Do you want to apply these changes? Only 'yes' will be accepted: yes
   📄 Ensuring page: example (placeholder)
   ✓ Page 'example' exists (ID: 32047105)
   📄 Ensuring page: CCFM Example (placeholder)
   ✓ Page 'CCFM Example' exists (ID: 32079873)
   📄 Ensuring page: My Team (placeholder)
   ✨ Creating page: My Team

📄 Processing: my_team.md
   Title: CCFM Example - My Team
   Status: current
   ✨ Creating new page
   👤 Author: CCFM Example Files
   🏷️  Labels: ccfm, reference, example, author-ccfm-example-files, managed-by-ci
   ✅ Success! Page ID: 32014339
   ℹ Attachment already exists (ID: att13140117), updating...

Apply complete!
❯ ccfm --config tests/smoke/ccfm-smoke.yaml apply --file "tests/smoke/docs/example/CCFM Example/complete_example.md"
Looking up space: CCFMDEV
   Space ID: 524292

No changes. Your Confluence pages are up to date.

No changes to apply.
❯ ccfm --config tests/smoke/ccfm-smoke.yaml apply --file "tests/smoke/docs/example/CCFM Example/complete_example.md" --force
Looking up space: CCFMDEV
   Space ID: 524292

ccfm will perform the following actions:

+ tests/smoke/docs/example/CCFM Example/complete_example.md (add)        "CCFM Example Files - Complete Element Reference"

Plan: 1 to add.

Do you want to apply these changes? Only 'yes' will be accepted: yes
   📄 Ensuring page: example (placeholder)
   ✓ Page 'example' exists (ID: 32047105)
   📄 Ensuring page: CCFM Example (placeholder)
   ✓ Page 'CCFM Example' exists (ID: 32079873)

📄 Processing: complete_example.md
   Title: CCFM Example Files - Complete Element Reference
   Status: current
   ♻️  Updating existing page (ID: 32112641)
   👤 Author: Platform Team
   🏷️  Labels: ccfm, reference, example, author-platform-team, managed-by-ci
   📎 Uploading: CCFM.png
   ℹ Attachment already exists (ID: att32047124), updating...
   🔑 Fetching Media Services fileId...
   ✓ Attachment ready: CCFM.png
   🔗 Resolving attachment media nodes...
   ✓ Page updated with 1 attachment(s)
   ✅ Success! Page ID: 32112641
   ℹ Attachment already exists (ID: att13140117), updating...

Apply complete!
