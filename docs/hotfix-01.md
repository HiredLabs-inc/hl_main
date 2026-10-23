Based on a thorough investigation of your Cloud Run service hl-stage-web in the hl-main-stage project, here is the exact diagnosis of why your site is hanging and failing to load.

1. Factual Log Analysis & Sequence of Events
We analyzed the latest log streams (including stdout, stderr, and request logs) for the active revision hl-stage-web-00024-m7v. A clear timeline of the hang was identified:

15:19:37Z – An incoming request to /agents/ triggers a container cold-start (Autoscaling spin-up).
15:19:39Z – Gunicorn boots up and successfully starts listening on port 8080.
15:19:57Z – Your application execution triggers the NLTK (Natural Language Toolkit) downloader to fetch stopwords:
[nltk_data] Downloading package stopwords to /root/nltk_data...
[nltk_data] Unzipping corpora/stopwords.zip.
15:19:57Z onwards – Complete silence. No further application logs are produced.
15:24:56Z (300 seconds later) – The initial request and all subsequent concurrent requests (e.g., to /staff/ or /agents/runs/) hit the maximum Cloud Run request timeout (300s) and are forcibly terminated with an HTTP 504 Gateway Timeout:
"The request has been terminated because it has reached the maximum request timeout."

2. Why is it hanging? (The Root Cause)
The hang is caused by executing nltk.download('stopwords') dynamically at runtime (either inside a Django view or during a module import triggered by the first request):

Concurrency Deadlock / Thread Blocking: Your Cloud Run service has its container concurrency limit set to 80. When multiple requests hit the cold-starting container simultaneously, they all try to download and extract the same zip file to /root/nltk_data/ at the same time. This causes write/file locks, thread blocks, or an infinite wait.
Network & Gateway Delays: Downloading packages at runtime over the public internet during a client request introduces unpredictable latency. If the external NLTK servers are slow or experience socket timeouts, your container thread remains blocked indefinitely.

3. Resolution (2026-10-23)
The concurrency theory above was a guess; the actual cause was simpler. `cold_apply/static/scripts/resume_writer/vars.py` called `nltk.download("stopwords")` when it was imported, and Django imports it on the first request to a new instance. The Dockerfile already put stopwords in the image at /usr/local/nltk_data, but ubuntu's system Python doesn't search that path, so NLTK downloaded them again at runtime.
Fix (698d0fe, merged into develop in bafc8f4, pushed to staging): the Dockerfile sets `NLTK_DATA=/usr/local/nltk_data`, and the runtime download is removed. Verified offline in the image; cold_apply tests pass. Goes to prod with the next release.
Related NLTK data that isn't in the image (unused today): BUG-043.
