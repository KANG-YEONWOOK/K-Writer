# Proposal to Change How We Review Code

I propose that from December 1 to December 31 we pilot a new review process in the payment service repository: two reviewers are assigned automatically when a PR is opened, and any PR that changes more than 500 lines is split before it is opened. In the third quarter, 131 of our 412 PRs (32%) waited more than 24 hours for a first review, and 18 PRs were merged with no review at all.

Today our team assigns no reviewer when a PR is opened. The link is posted in the team channel and anyone may review it. I believe first reviews are late because nobody is designated to review a given PR, so each person leaves it to someone else. Large PRs, those that change 500 lines or more, wait the longest: they account for 74 of the 131 PRs that waited more than 24 hours.

Under the new process, the two reviewers are chosen by weekly rotation, based on the code owners file. If a PR over 500 lines cannot be split, the reason is written in the PR description.

During the pilot we will track the median time to first review and the share of PRs that wait more than 24 hours for it. In the third quarter this median was 9.5 hours.

Automatic assignment is not yet linked to the vacation calendar, so the rotation can land on someone who is on vacation. During the pilot, the reviewer will be changed by hand when that happens.

The pilot needs your approval and permission to change the repository settings. That permission has to be requested from the infrastructure team and takes one day to get. Please decide by Wednesday, November 25, whether to approve the pilot.
