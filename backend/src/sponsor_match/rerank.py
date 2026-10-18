"""Offline-only experiment. This does not enable live reranking."""
from time import perf_counter
from .evaluate import metrics


def benchmark(inputs,labels):
    from sentence_transformers import CrossEncoder
    model=CrossEncoder("cross-encoder/ms-marco-MiniLM-L6-v2",max_length=512)
    baseline,ranked,timings={},{},[]
    for item in inputs:
        candidates=item["candidates"][:60]
        id=item["profile_id"]
        baseline[id]=[c["employer_id"] for c in candidates]
        if not candidates:
            ranked[id]=[];continue
        start=perf_counter()
        scores=model.predict([(item["professional_query"],c["evidence_text"]) for c in candidates],batch_size=16)
        timings.append((perf_counter()-start)*1000)
        ranked[id]=[c["employer_id"] for c,s in sorted(zip(candidates,scores),key=lambda pair:float(pair[1]),reverse=True)]
    ordered=sorted(timings)
    return {"baseline":metrics(baseline,labels),"reranked":metrics(ranked,labels),"p95_model_ms":ordered[min(len(ordered)-1,int(.95*len(ordered)))] if ordered else None,"live_reranking_enabled":False,"gate":"Requires >=5% relative held-out NDCG gain, unchanged preview precision/attribution, occupational coverage and p95 <500ms on deployed hardware."}
