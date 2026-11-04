# Internal note: moving the sync agent from Python to Rust

This note is fictional material written for a writing evaluation. Do not cite it as a real result.

## Why we built a second version

The sync agent runs on about 4,000 company laptops. The Python version has been in production since 2023. It used 210 MB of memory at idle and took 1.9 seconds to start, so in March the team started building a Rust version. The team owns both versions until the migration ends.

## Two versions side by side

For six weeks the installer shipped both versions. Version 1.8 was the last Python version and version 2.0 was the first Rust version. The old version and the new version read the same configuration file, so a laptop could move to the new version and back without losing settings.

At startup the new version reads the installed version number from the registry and refuses to run if that version is older than 1.6. The installer keeps a copy of the old binary next to the new one, so rolling back to the previous version takes 40 seconds and needs no download. The latest version is always published to the update server, and each patch version only changes the third number, for example 2.0.3.

## Bugs and tests

The test suite has 1,240 tests. On the first Rust build 31 tests failed. Nine of those also failed on the old version, so they were not regressions. The other 22 were real bugs. The worst bug was in the file watcher: when a user renamed a folder, the new version missed every later change inside it. The fix shipped in version 2.0.3, and the test suite now covers the rename path. The tests still do not cover network drives.

While a sync runs, the agent holds a lock on the database file. The update checker reads the HTTP response header, updates the local cache, and returns the latest version string. Each worker has a hard limit of 8 open files. After a crash, the remaining entries in the queue are replayed in order.

## The design document

The first draft of the design document was wrong about how the lock works, so the second version removed that section. Reviewers compared the current version of the document with the version in the HEAD commit. Words like "sync" and "commit" had two meanings in the draft, so the authors kept one meaning for each word and paired every term with a short definition. They repeated this check for each section and excluded the appendix.

## What the paper said

The team used a benchmark from Lee et al. (2024) to compare file-watching libraries. The arXiv version and the published IEEE version of that paper number their equations differently, so this note uses the numbering in the published version. Among the 12 libraries in the benchmark, three support Windows junctions. The paper reports the strength of the link between watch count and memory use as r = 0.91.

## Results

We measured the Rust version on 500 laptops for two weeks. Idle memory fell from 210 MB to 38 MB, and startup time fell from 1.9 seconds to 0.3 seconds. The binary emits one log line per sync, down from about 40 in the old version. About 120 laptops still run the old version because a security tool blocks the new binary. We do not know yet whether the new version behaves the same on network drives, because nobody has tested it there.
