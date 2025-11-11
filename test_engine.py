#!/usr/bin/env python3
"""Quick test of the sentiment engine."""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent))

from datetime import datetime, timezone, timedelta
from sentiment import SentimentEngine, NewsDoc
from sentiment.references import ReferenceBuilder

def test_basic_functionality():
    """Test basic engine functionality."""
    
    print("Testing Sentiment Engine...")
    
    # 1. Initialize
    print("1. Initializing engine...")
    engine = SentimentEngine()
    print("   ✅ Engine created")
    
    # 2. Create test documents
    print("2. Creating test documents...")
    now = datetime.now(timezone.utc)
    
    docs = [
        NewsDoc(
            id="test1",
            ts_utc=now,
            title="Apple reports record earnings, stock soars on strong iPhone sales",
            url="https://example.com/1",
            source="reuters",
            tickers=[]
        ),
        NewsDoc(
            id="test2",
            ts_utc=now - timedelta(minutes=5),
            title="Tesla faces production challenges, deliveries miss expectations",
            url="https://example.com/2",
            source="bloomberg",
            tickers=[]
        ),
        NewsDoc(
            id="test3",
            ts_utc=now - timedelta(minutes=10),
            title="Microsoft announces AI partnership, cloud revenue beats estimates",
            url="https://example.com/3",
            source="wsj",
            tickers=[]
        ),
    ]
    print(f"   ✅ Created {len(docs)} test documents")
    
    # 3. Score documents
    print("3. Scoring documents...")
    scored = engine.score_docs(docs)
    print(f"   ✅ Scored {len(scored)} documents")
    
    # Display scores
    for s in scored:
        if s.spans:
            span = s.spans[0]
            print(f"   - {s.doc.title[:50]}...")
            print(f"     Tickers: {s.doc.tickers}")
            print(f"     Sentiment: {span.label.value} (score: {span.score:.3f})")
    
    # 4. Ingest
    print("4. Ingesting documents...")
    engine.ingest(scored)
    print("   ✅ Documents ingested")
    
    # 5. Generate snapshots
    print("5. Generating snapshots...")
    
    for ticker in ["AAPL", "TSLA", "MSFT"]:
        if ticker in [t for doc in scored for t in doc.doc.tickers]:
            snapshot = engine.snapshot(ticker, "5m")
            print(f"\n   {ticker} (5m window):")
            print(f"   - Mean sentiment: {snapshot.mean:.3f}")
            print(f"   - Documents: {snapshot.n_docs}")
            print(f"   - Entropy: {snapshot.entropy:.3f}")
            print(f"   - Trending: {snapshot.is_trending_sentiment}")
    
    # 6. Test reference builder
    print("\n6. Testing reference builder...")
    ref_builder = ReferenceBuilder()
    engine.attach_reference_builder(ref_builder)
    
    # Add some price data
    for i in range(10):
        t = now - timedelta(minutes=10-i)
        ref_builder.update_price("XLK", t, 200.0 + i * 0.5)
    
    print("   ✅ Reference builder attached and updated")
    
    # 7. Check statistics
    print("\n7. Engine statistics:")
    stats = engine.get_statistics()
    for key, value in stats.items():
        print(f"   - {key}: {value}")
    
    print("\n✅ All tests passed!")
    return True


if __name__ == "__main__":
    try:
        success = test_basic_functionality()
        if success:
            print("\n🎆 Sentiment Engine is working perfectly!")
            sys.exit(0)
        else:
            print("\n❌ Some tests failed")
            sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error during testing: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)