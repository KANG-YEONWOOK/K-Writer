# Why the search indexer moved to batching, and what happened

The search indexer is the program that turns each product listing a seller uploads into an entry in the search index, and the search infrastructure team is responsible for it. The indexer handles each listing as one document, and until April it processed one document at a time. It now uses batching, which means it groups several documents and stores them in a single write. As a result, the time it takes for an uploaded listing to become searchable fell from 9 minutes to 2 minutes in the Busan cluster.

The indexer was changed because the time documents waited in the queue accounted for 70% of index lag. Index lag is the time from when a seller uploads a listing until that listing can be found in search. Index state is stored in object storage, and before the change the indexer had to send a separate write request to object storage for every document it processed.

After the change, the indexer groups up to 200 documents into one batch and stores the batch in object storage with a single write request. Workers use 60% of their CPU time decompressing documents, and compressing a batch adds about 3 ms of overhead per document.

Once batching was in place, a new problem appeared: when one document in a batch failed validation, the whole batch was rejected. The problem was tracked in ticket SEARCH-311, and the fix retries only the document that failed validation. After the fix was included in v4.1, the problem was resolved and ticket SEARCH-311 was closed.

v4.1 was released in June. The schema registry added in v4.1 also makes it possible to carry out the migrations of older listing formats that had not been finished.

The listing team is responsible for the upload client, the program sellers use to upload listings. The new upload client shows indexing errors to the seller, so the seller can see which listing failed to be indexed and why.

Ticket SEARCH-327 reported duplicate documents in the index, but it was closed with a decision not to fix the problem. It was not fixed because duplicates appeared in fewer than 0.01% of search queries and the next full reindex will remove them.

After batching was applied, index lag in the Busan cluster fell from 9 minutes to 2 minutes. Index lag in the Seoul cluster stayed at 1.5 minutes, the same as before batching, so most of the difference in index lag between the two clusters disappeared. The peak number of write requests to object storage also fell by 85%.

It has not yet been confirmed whether batching works well for listings that contain images larger than 5 MB. So far, batching has been tested only with listings without images. For urgent listings, the option of a smaller batch size, meaning fewer documents grouped into one batch, has been kept open.
