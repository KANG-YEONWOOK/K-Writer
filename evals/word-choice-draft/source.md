# Internal note: batching in the search indexer

This note is fictional material written for a writing evaluation. Do not cite it as a real result.

## Why we changed the indexer

Sellers upload product listings, and the search indexer turns each listing into an entry in the search index. Until April, the indexer processed one document at a time. Index state lives in object storage, and every document required a separate write to object storage. Index lag, the time between an upload and the moment the listing becomes searchable, was dominated by queueing time: documents spent 70% of the lag waiting in the queue.

The search infrastructure team owns the indexer. The listing team owns the upload client.

## The batching change

The team grouped up to 200 documents into one write. Workers spend 60% of their CPU time decompressing documents, and compressing a batch introduces about 3 ms of overhead per document.

Batching opened up a new problem: when one document in a batch failed validation, the whole batch was rejected. Ticket SEARCH-311 tracked this problem, and it was closed after the fix landed in v4.1. The fix retries only the failed document. The team shipped v4.1 in June.

The new upload client surfaces indexing errors to the seller, so a seller sees which listing failed and why. The schema registry added in v4.1 also unblocks the remaining migrations of older listing formats.

A report of duplicate documents in the index (SEARCH-327) was closed as won't fix, because duplicates appeared in fewer than 0.01% of queries and the next full reindex removes them.

## Results

Batching closed most of the gap between the two clusters: index lag in the Busan cluster fell from 9 minutes to 2 minutes, while the Seoul cluster stayed at 1.5 minutes. Peak write requests to object storage fell by 85%.

## What we don't know yet

Whether the approach works for listings with images larger than 5 MB remains an open question; the team has only tested listings without images. The team kept the option of a smaller batch size for urgent listings open.
