#!/usr/bin/env python3
"""Demo of the production sentiment engine."""

import asyncio
from datetime import datetime, timezone, timedelta
import logging
from rich.console import Console
from rich.table import Table
from rich import print as rprint

# Add parent directory to path for imports
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from sentiment import SentimentEngine, NewsDoc
from sentiment.references import ReferenceBuilder
from sentiment.fetchers import GoogleRSSFetcher

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

console = Console()


async def main():
    """Run sentiment engine demo."""
    
    # ============= Initialize Engine =============
    console.print("[bold green]Initializing Sentiment Engine...[/bold green]")
    
    # Define symbol aliases
    aliases = {
        "AAPL": {"Apple", "Apple Inc.", "Apple Inc"},
        "MSFT": {"Microsoft", "Microsoft Corp", "Microsoft Corporation"},
        "GOOGL": {"Google", "Alphabet", "Alphabet Inc"},
        "TSLA": {"Tesla", "Tesla Inc", "Tesla Motors"},
        "NVDA": {"NVIDIA", "Nvidia", "NVIDIA Corporation"},
        "META": {"Meta", "Facebook", "Meta Platforms"},
        "AMZN": {"Amazon", "Amazon.com", "Amazon Inc"},
    }
    
    # Create engine
    engine = SentimentEngine(symbol_aliases=aliases)
    
    # ============= Setup References =============
    console.print("[bold blue]Setting up reference builder...[/bold blue]")
    
    # Create reference builder for sector ETFs
    ref_builder = ReferenceBuilder()
    engine.attach_reference_builder(ref_builder)
    
    # Map tickers to sectors
    tech_stocks = ["AAPL", "MSFT", "GOOGL", "NVDA", "META"]
    for ticker in tech_stocks:
        engine.set_ticker_reference(ticker, "XLK")  # Tech sector ETF
    
    engine.set_ticker_reference("TSLA", "XLY")  # Consumer discretionary
    engine.set_ticker_reference("AMZN", "XLY")
    
    # Simulate some ETF price data
    now = datetime.now(timezone.utc)
    etf_prices = {
        "XLK": [200.0, 200.5, 200.2, 201.0, 201.6, 201.3, 202.1, 202.5],
        "XLY": [150.0, 149.8, 150.2, 150.5, 151.0, 150.8, 151.2, 151.5],
        "SPY": [450.0, 450.5, 450.3, 451.0, 451.5, 451.2, 452.0, 452.3],
    }
    
    for i in range(len(etf_prices["XLK"])):
        timestamp = now - timedelta(hours=8-i)
        for etf, prices in etf_prices.items():
            ref_builder.update_price(etf, timestamp, prices[i])
    
    # ============= Fetch News =============
    console.print("[bold yellow]Fetching news articles...[/bold yellow]")
    
    fetcher = GoogleRSSFetcher()
    
    # Fetch news for different queries
    queries = [
        "Apple stock",
        "Microsoft earnings",
        "Tesla delivery",
        "NVIDIA AI",
        "tech stocks market",
    ]
    
    all_docs = []
    for query in queries:
        console.print(f"  Fetching: {query}")
        docs = await fetcher.fetch(query, max_articles=5)
        all_docs.extend(docs)
    
    console.print(f"[green]Fetched {len(all_docs)} articles[/green]")
    
    # ============= Score Documents =============
    console.print("\n[bold cyan]Scoring documents...[/bold cyan]")
    
    scored_docs = engine.score_docs(all_docs)
    console.print(f"[green]Scored {len(scored_docs)} documents[/green]")
    
    # Display some scored results
    if scored_docs:
        table = Table(title="Sample Scored Documents")
        table.add_column("Title", style="cyan", width=50)
        table.add_column("Tickers", style="yellow")
        table.add_column("Sentiment", style="green")
        table.add_column("Score", style="magenta")
        
        for scored in scored_docs[:5]:
            if scored.spans:
                span = scored.spans[0]
                table.add_row(
                    scored.doc.title[:50] + ".." if len(scored.doc.title) > 50 else scored.doc.title,
                    ", ".join(scored.doc.tickers[:3]),
                    span.label.value,
                    f"{span.score:.3f}"
                )
        
        console.print(table)
    
    # ============= Ingest into Engine =============
    console.print("\n[bold magenta]Ingesting scored documents...[/bold magenta]")
    
    engine.ingest(scored_docs)
    
    # ============= Generate Snapshots =============
    console.print("\n[bold green]Generating sentiment snapshots...[/bold green]")
    
    # Get snapshots for tracked tickers
    tracked_tickers = ["AAPL", "MSFT", "TSLA", "NVDA"]
    
    for ticker in tracked_tickers:
        console.print(f"\n[bold]{ticker} Sentiment Analysis:[/bold]")
        
        snapshots = engine.snapshots_for(ticker)
        
        # Create table for this ticker
        table = Table(title=f"{ticker} Metrics")
        table.add_column("Window", style="cyan")
        table.add_column("Mean", style="yellow")
        table.add_column("Momentum", style="green")
        table.add_column("Entropy", style="magenta")
        table.add_column("Surprise", style="blue")
        table.add_column("Market Corr", style="red")
        table.add_column("Flags", style="white")
        
        for window, snap in snapshots.items():
            flags = []
            if snap.is_trending_sentiment:
                flags.append("📈")
            if snap.is_information_shock:
                flags.append("⚡")
            if snap.is_contrarian_market:
                flags.append("🔄")
            
            table.add_row(
                window,
                f"{snap.mean:.3f}",
                f"{snap.momentum:.3f}",
                f"{snap.entropy:.3f}",
                f"{snap.surprise:.3f}",
                f"{snap.corr_to_market:.3f}" if snap.corr_to_market else "N/A",
                " ".join(flags) if flags else "-"
            )
        
        console.print(table)
        
        # Print key insights
        snap_1h = snapshots.get("1h")
        if snap_1h and snap_1h.n_docs > 0:
            console.print(f"\n[dim]Insights for {ticker}:[/dim]")
            
            if snap_1h.mean > 0.1:
                console.print("  • [green]Positive sentiment detected[/green]")
            elif snap_1h.mean < -0.1:
                console.print("  • [red]Negative sentiment detected[/red]")
            else:
                console.print("  • [yellow]Neutral sentiment[/yellow]")
            
            if snap_1h.is_information_shock:
                console.print("  • [bold yellow]⚡ Information shock detected![/bold yellow]")
            
            if snap_1h.is_contrarian_market:
                console.print("  • [bold cyan]🔄 Contrarian to market[/bold cyan]")
            
            if snap_1h.entropy > 0.7:
                console.print("  • [magenta]High uncertainty (mixed signals)[/magenta]")
    
    # ============= Display Statistics =============
    console.print("\n[bold white]Engine Statistics:[/bold white]")
    stats = engine.get_statistics()
    
    for key, value in stats.items():
        console.print(f"  {key}: {value}")
    
    console.print("\n[bold green]✅ Demo completed successfully![/bold green]")


if __name__ == "__main__":
    asyncio.run(main())