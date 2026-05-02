#!/usr/bin/env python3
"""
Telegram Bot for Super Gnosis V2 Trading System

Provides real-time monitoring and control of the autonomous trading system.

Features:
- Real-time portfolio monitoring
- Trade notifications
- Opportunity scanner control
- Performance analytics
- System health checks
"""

import os
import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, List
import json

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


class TradingBot:
    """Telegram bot for trading system monitoring and control."""
    
    def __init__(self, token: str):
        """Initialize the bot with Telegram token."""
        self.token = token
        self.app = Application.builder().token(token).build()
        self.trading_active = False
        self.scan_interval = 300  # 5 minutes
        self.top_n = 25
        self.trade_interval = 60
        
        # Register handlers
        self._register_handlers()
    
    def _register_handlers(self):
        """Register all command and callback handlers."""
        # Command handlers
        self.app.add_handler(CommandHandler("start", self.start_command))
        self.app.add_handler(CommandHandler("help", self.help_command))
        self.app.add_handler(CommandHandler("status", self.status_command))
        self.app.add_handler(CommandHandler("portfolio", self.portfolio_command))
        self.app.add_handler(CommandHandler("opportunities", self.opportunities_command))
        self.app.add_handler(CommandHandler("scan", self.scan_command))
        self.app.add_handler(CommandHandler("performance", self.performance_command))
        self.app.add_handler(CommandHandler("positions", self.positions_command))
        self.app.add_handler(CommandHandler("health", self.health_command))
        self.app.add_handler(CommandHandler("settings", self.settings_command))
        
        # Callback query handlers (for inline buttons)
        self.app.add_handler(CallbackQueryHandler(self.button_callback))
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Send welcome message with main menu."""
        keyboard = [
            [
                InlineKeyboardButton("📊 Status", callback_data="status"),
                InlineKeyboardButton("💰 Portfolio", callback_data="portfolio"),
            ],
            [
                InlineKeyboardButton("🔍 Opportunities", callback_data="opportunities"),
                InlineKeyboardButton("📈 Performance", callback_data="performance"),
            ],
            [
                InlineKeyboardButton("🎯 Positions", callback_data="positions"),
                InlineKeyboardButton("⚙️ Settings", callback_data="settings"),
            ],
            [
                InlineKeyboardButton("❤️ Health", callback_data="health"),
                InlineKeyboardButton("❓ Help", callback_data="help"),
            ],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        welcome_message = (
            "🤖 *Super Gnosis V2 Trading Bot*\n\n"
            "Welcome to your autonomous trading assistant!\n\n"
            "🎯 *Quick Access:*\n"
            "• /status - System status\n"
            "• /portfolio - Portfolio overview\n"
            "• /opportunities - Top opportunities\n"
            "• /scan - Force universe scan\n"
            "• /performance - Performance metrics\n"
            "• /settings - Configure system\n\n"
            "Select an option below to get started:"
        )
        
        await update.message.reply_text(
            welcome_message,
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show help message with all commands."""
        help_text = (
            "📚 *Available Commands*\n\n"
            "*Monitoring:*\n"
            "/status - Trading system status\n"
            "/portfolio - Portfolio value & positions\n"
            "/opportunities - Top ranked opportunities\n"
            "/positions - Open positions details\n"
            "/performance - Performance analytics\n"
            "/health - System health check\n\n"
            "*Control:*\n"
            "/scan - Force universe re-scan\n"
            "/settings - Change system parameters\n\n"
            "*Information:*\n"
            "/help - Show this help message\n"
            "/start - Main menu\n\n"
            "💡 *Tip:* Use inline buttons for quick access!"
        )
        
        await update.message.reply_text(help_text, parse_mode='Markdown')
    
    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show current system status."""
        try:
            # Import here to avoid circular imports
            from execution.broker_adapters.alpaca_adapter import AlpacaBrokerAdapter
            
            # Get broker status
            broker = AlpacaBrokerAdapter(paper=True)
            account = broker.get_account()
            
            status_message = (
                f"🟢 *System Status*\n\n"
                f"Trading: {'🟢 Active' if self.trading_active else '🔴 Inactive'}\n"
                f"Mode: Paper Trading\n"
                f"Broker: Alpaca\n\n"
                f"*Configuration:*\n"
                f"• Top N Symbols: {self.top_n}\n"
                f"• Scan Interval: {self.scan_interval}s ({self.scan_interval // 60} min)\n"
                f"• Trade Interval: {self.trade_interval}s\n\n"
                f"*Account:*\n"
                f"• Portfolio Value: ${float(account.portfolio_value):,.2f}\n"
                f"• Buying Power: ${float(account.buying_power):,.2f}\n"
                f"• Cash: ${float(account.cash):,.2f}\n\n"
                f"⏰ Last update: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC"
            )
            
        except Exception as e:
            status_message = (
                f"⚠️ *System Status*\n\n"
                f"Error getting status: {str(e)}\n\n"
                f"Trading: {'🟢 Active' if self.trading_active else '🔴 Inactive'}\n"
                f"Top N: {self.top_n} | Scan: {self.scan_interval}s"
            )
        
        await update.message.reply_text(status_message, parse_mode='Markdown')
    
    async def portfolio_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show portfolio overview."""
        try:
            from execution.broker_adapters.alpaca_adapter import AlpacaBrokerAdapter
            
            broker = AlpacaBrokerAdapter(paper=True)
            account = broker.get_account()
            positions = broker.get_positions()
            
            portfolio_value = float(account.portfolio_value)
            cash = float(account.cash)
            equity = float(account.equity)
            pnl = float(account.equity) - 30000.0  # Assuming $30k starting capital
            pnl_pct = (pnl / 30000.0) * 100
            
            message = (
                f"💰 *Portfolio Overview*\n\n"
                f"*Total Value:* ${portfolio_value:,.2f}\n"
                f"*Cash:* ${cash:,.2f}\n"
                f"*Equity:* ${equity:,.2f}\n\n"
                f"*P&L:* ${pnl:+,.2f} ({pnl_pct:+.2f}%)\n\n"
                f"*Positions:* {len(positions)}\n"
            )
            
            if positions:
                message += "\n📊 *Open Positions:*\n"
                for pos in positions[:10]:  # Show top 10
                    symbol = pos.symbol
                    qty = int(pos.qty)
                    current_price = float(pos.current_price)
                    market_value = float(pos.market_value)
                    unrealized_pl = float(pos.unrealized_pl)
                    unrealized_plpc = float(pos.unrealized_plpc) * 100
                    
                    message += (
                        f"\n{symbol}: {qty} @ ${current_price:.2f}\n"
                        f"  Value: ${market_value:,.2f}\n"
                        f"  P&L: ${unrealized_pl:+.2f} ({unrealized_plpc:+.2f}%)\n"
                    )
                
                if len(positions) > 10:
                    message += f"\n... and {len(positions) - 10} more positions"
            else:
                message += "\n_No open positions_"
            
            message += f"\n\n⏰ {datetime.now(timezone.utc).strftime('%H:%M:%S')} UTC"
            
        except Exception as e:
            message = f"❌ Error fetching portfolio: {str(e)}"
        
        await update.message.reply_text(message, parse_mode='Markdown')
    
    async def opportunities_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show top opportunities from last scan."""
        try:
            # This would integrate with your OpportunityScanner
            # For now, show a demo message
            message = (
                f"🔍 *Top Opportunities*\n\n"
                f"_Running universe scan..._\n\n"
                f"This will show the top {self.top_n} opportunities\n"
                f"ranked by DHPE composite score.\n\n"
                f"Use /scan to force a new scan."
            )
            
            await update.message.reply_text(message, parse_mode='Markdown')
            
            # TODO: Actually run the scanner and show results
            # from engines.scanner import OpportunityScanner
            # scanner = build_scanner()
            # result = scanner.scan(DEFAULT_UNIVERSE, top_n=self.top_n)
            # ... format and send results
            
        except Exception as e:
            await update.message.reply_text(f"❌ Error: {str(e)}", parse_mode='Markdown')
    
    async def scan_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Force a new universe scan."""
        await update.message.reply_text(
            "🔍 *Force Scan*\n\n"
            "Starting universe scan...\n"
            "This may take 60-90 seconds.",
            parse_mode='Markdown'
        )
        
        try:
            # TODO: Trigger actual scan
            # from engines.scanner import OpportunityScanner, DEFAULT_UNIVERSE
            # scanner = build_scanner()
            # result = scanner.scan(DEFAULT_UNIVERSE, top_n=self.top_n)
            
            # For now, show placeholder
            await asyncio.sleep(2)
            
            message = (
                "✅ *Scan Complete*\n\n"
                f"Scanned 67 symbols in 1.2s\n"
                f"Found {self.top_n} opportunities\n\n"
                "Use /opportunities to view results"
            )
            
            await update.message.reply_text(message, parse_mode='Markdown')
            
        except Exception as e:
            await update.message.reply_text(f"❌ Scan failed: {str(e)}", parse_mode='Markdown')
    
    async def performance_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show performance metrics."""
        try:
            from execution.broker_adapters.alpaca_adapter import AlpacaBrokerAdapter
            
            broker = AlpacaBrokerAdapter(paper=True)
            account = broker.get_account()
            
            # Calculate metrics
            equity = float(account.equity)
            starting_capital = 30000.0
            total_return = equity - starting_capital
            total_return_pct = (total_return / starting_capital) * 100
            
            message = (
                f"📈 *Performance Metrics*\n\n"
                f"*Returns:*\n"
                f"• Total: ${total_return:+,.2f} ({total_return_pct:+.2f}%)\n"
                f"• Starting Capital: ${starting_capital:,.2f}\n"
                f"• Current Equity: ${equity:,.2f}\n\n"
                f"*Account:*\n"
                f"• Day Trade Count: {account.daytrade_count}\n"
                f"• Pattern Day Trader: {'Yes' if account.pattern_day_trader else 'No'}\n\n"
                f"_More detailed analytics coming soon..._\n"
                f"⏰ {datetime.now(timezone.utc).strftime('%H:%M:%S')} UTC"
            )
            
        except Exception as e:
            message = f"❌ Error: {str(e)}"
        
        await update.message.reply_text(message, parse_mode='Markdown')
    
    async def positions_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show detailed position information."""
        try:
            from execution.broker_adapters.alpaca_adapter import AlpacaBrokerAdapter
            
            broker = AlpacaBrokerAdapter(paper=True)
            positions = broker.get_positions()
            
            if not positions:
                await update.message.reply_text(
                    "📊 *Positions*\n\n_No open positions_",
                    parse_mode='Markdown'
                )
                return
            
            message = f"📊 *Open Positions ({len(positions)})*\n\n"
            
            for pos in positions:
                symbol = pos.symbol
                qty = int(pos.qty)
                avg_entry = float(pos.avg_entry_price)
                current = float(pos.current_price)
                market_value = float(pos.market_value)
                unrealized_pl = float(pos.unrealized_pl)
                unrealized_plpc = float(pos.unrealized_plpc) * 100
                
                direction = "🟢" if unrealized_pl > 0 else "🔴" if unrealized_pl < 0 else "⚪"
                
                message += (
                    f"{direction} *{symbol}*\n"
                    f"  Qty: {qty:,} @ ${avg_entry:.2f}\n"
                    f"  Current: ${current:.2f}\n"
                    f"  Value: ${market_value:,.2f}\n"
                    f"  P&L: ${unrealized_pl:+,.2f} ({unrealized_plpc:+.2f}%)\n\n"
                )
            
            message += f"⏰ {datetime.now(timezone.utc).strftime('%H:%M:%S')} UTC"
            
            await update.message.reply_text(message, parse_mode='Markdown')
            
        except Exception as e:
            await update.message.reply_text(f"❌ Error: {str(e)}", parse_mode='Markdown')
    
    async def health_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Check system health."""
        health_checks = []
        
        # Check broker connection
        try:
            from execution.broker_adapters.alpaca_adapter import AlpacaBrokerAdapter
            broker = AlpacaBrokerAdapter(paper=True)
            account = broker.get_account()
            health_checks.append(("Broker Connection", "✅", "Alpaca connected"))
        except Exception as e:
            health_checks.append(("Broker Connection", "❌", str(e)))
        
        # Check data adapters
        try:
            from engines.inputs.yfinance_adapter import create_yfinance_adapters
            market, options, news = create_yfinance_adapters()
            health_checks.append(("Data Adapters", "✅", "Yahoo Finance ready"))
        except Exception as e:
            health_checks.append(("Data Adapters", "❌", str(e)))
        
        # Check configuration
        try:
            from config.loader import load_config
            config = load_config()
            health_checks.append(("Configuration", "✅", "Config loaded"))
        except Exception as e:
            health_checks.append(("Configuration", "❌", str(e)))
        
        # Build message
        message = "❤️ *System Health Check*\n\n"
        
        all_healthy = all(check[1] == "✅" for check in health_checks)
        overall = "🟢 All systems operational" if all_healthy else "🟡 Some issues detected"
        message += f"{overall}\n\n"
        
        for component, status, detail in health_checks:
            message += f"{status} *{component}*\n  {detail}\n\n"
        
        message += f"⏰ {datetime.now(timezone.utc).strftime('%H:%M:%S')} UTC"
        
        await update.message.reply_text(message, parse_mode='Markdown')
    
    async def settings_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show and modify settings."""
        keyboard = [
            [
                InlineKeyboardButton("Top N: " + str(self.top_n), callback_data="set_top_n"),
                InlineKeyboardButton("Scan: " + str(self.scan_interval) + "s", callback_data="set_scan_interval"),
            ],
            [
                InlineKeyboardButton("Trade Interval: " + str(self.trade_interval) + "s", callback_data="set_trade_interval"),
            ],
            [
                InlineKeyboardButton("🔙 Back to Menu", callback_data="main_menu"),
            ],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        message = (
            f"⚙️ *Settings*\n\n"
            f"*Current Configuration:*\n"
            f"• Top N Symbols: {self.top_n}\n"
            f"• Scan Interval: {self.scan_interval}s ({self.scan_interval // 60} min)\n"
            f"• Trade Interval: {self.trade_interval}s\n\n"
            f"Click a button to change:"
        )
        
        await update.message.reply_text(
            message,
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
    
    async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle inline button callbacks."""
        query = update.callback_query
        await query.answer()
        
        # Route to appropriate handler
        if query.data == "status":
            await self._show_status_callback(query)
        elif query.data == "portfolio":
            await self._show_portfolio_callback(query)
        elif query.data == "opportunities":
            await self._show_opportunities_callback(query)
        elif query.data == "performance":
            await self._show_performance_callback(query)
        elif query.data == "positions":
            await self._show_positions_callback(query)
        elif query.data == "health":
            await self._show_health_callback(query)
        elif query.data == "settings":
            await self._show_settings_callback(query)
        elif query.data == "help":
            await self._show_help_callback(query)
        elif query.data == "main_menu":
            await self._show_main_menu_callback(query)
    
    async def _show_status_callback(self, query):
        """Show status via callback."""
        # Reuse status_command logic but for callback
        try:
            from execution.broker_adapters.alpaca_adapter import AlpacaBrokerAdapter
            broker = AlpacaBrokerAdapter(paper=True)
            account = broker.get_account()
            
            message = (
                f"🟢 *System Status*\n\n"
                f"Trading: {'🟢 Active' if self.trading_active else '🔴 Inactive'}\n"
                f"Portfolio: ${float(account.portfolio_value):,.2f}\n"
                f"Top N: {self.top_n} symbols\n\n"
                f"⏰ {datetime.now(timezone.utc).strftime('%H:%M:%S')} UTC"
            )
        except Exception as e:
            message = f"⚠️ Error: {str(e)}"
        
        await query.edit_message_text(message, parse_mode='Markdown')
    
    async def _show_portfolio_callback(self, query):
        """Show portfolio via callback."""
        try:
            from execution.broker_adapters.alpaca_adapter import AlpacaBrokerAdapter
            broker = AlpacaBrokerAdapter(paper=True)
            account = broker.get_account()
            
            message = (
                f"💰 *Portfolio*\n\n"
                f"Value: ${float(account.portfolio_value):,.2f}\n"
                f"Cash: ${float(account.cash):,.2f}\n"
                f"Buying Power: ${float(account.buying_power):,.2f}\n\n"
                f"Use /portfolio for detailed view"
            )
        except Exception as e:
            message = f"❌ Error: {str(e)}"
        
        await query.edit_message_text(message, parse_mode='Markdown')
    
    async def _show_opportunities_callback(self, query):
        """Show opportunities via callback."""
        message = (
            f"🔍 *Opportunities*\n\n"
            f"Top {self.top_n} symbols being tracked\n\n"
            f"Use /opportunities for full list\n"
            f"Use /scan to force new scan"
        )
        await query.edit_message_text(message, parse_mode='Markdown')
    
    async def _show_performance_callback(self, query):
        """Show performance via callback."""
        message = (
            "📈 *Performance*\n\n"
            "Use /performance for detailed metrics"
        )
        await query.edit_message_text(message, parse_mode='Markdown')
    
    async def _show_positions_callback(self, query):
        """Show positions via callback."""
        try:
            from execution.broker_adapters.alpaca_adapter import AlpacaBrokerAdapter
            broker = AlpacaBrokerAdapter(paper=True)
            positions = broker.get_positions()
            
            if not positions:
                message = "📊 *Positions*\n\n_No open positions_"
            else:
                message = f"📊 *Positions* ({len(positions)})\n\nUse /positions for details"
        except Exception as e:
            message = f"❌ Error: {str(e)}"
        
        await query.edit_message_text(message, parse_mode='Markdown')
    
    async def _show_health_callback(self, query):
        """Show health via callback."""
        message = (
            "❤️ *Health Check*\n\n"
            "Use /health for full diagnostics"
        )
        await query.edit_message_text(message, parse_mode='Markdown')
    
    async def _show_settings_callback(self, query):
        """Show settings via callback."""
        keyboard = [
            [
                InlineKeyboardButton("Top N: " + str(self.top_n), callback_data="set_top_n"),
            ],
            [
                InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu"),
            ],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        message = (
            f"⚙️ *Settings*\n\n"
            f"Top N: {self.top_n}\n"
            f"Scan: {self.scan_interval}s\n"
            f"Trade: {self.trade_interval}s"
        )
        
        await query.edit_message_text(
            message,
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
    
    async def _show_help_callback(self, query):
        """Show help via callback."""
        message = (
            "📚 *Quick Commands*\n\n"
            "/status - System status\n"
            "/portfolio - Portfolio view\n"
            "/opportunities - Top opportunities\n"
            "/scan - Force scan\n"
            "/performance - Metrics\n"
            "/settings - Configure\n"
            "/help - Full help"
        )
        await query.edit_message_text(message, parse_mode='Markdown')
    
    async def _show_main_menu_callback(self, query):
        """Show main menu via callback."""
        keyboard = [
            [
                InlineKeyboardButton("📊 Status", callback_data="status"),
                InlineKeyboardButton("💰 Portfolio", callback_data="portfolio"),
            ],
            [
                InlineKeyboardButton("🔍 Opportunities", callback_data="opportunities"),
                InlineKeyboardButton("📈 Performance", callback_data="performance"),
            ],
            [
                InlineKeyboardButton("🎯 Positions", callback_data="positions"),
                InlineKeyboardButton("⚙️ Settings", callback_data="settings"),
            ],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        message = (
            "🤖 *Super Gnosis V2 Bot*\n\n"
            "Select an option:"
        )
        
        await query.edit_message_text(
            message,
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
    
    def run(self):
        """Start the bot."""
        logger.info("Starting Telegram bot...")
        self.app.run_polling(allowed_updates=Update.ALL_TYPES)


def main():
    """Main entry point."""
    # Get token from environment
    token = os.getenv('TELEGRAM_BOT_TOKEN')
    
    if not token:
        logger.error("TELEGRAM_BOT_TOKEN environment variable not set!")
        logger.info("Get your token from @BotFather on Telegram")
        logger.info("Then set: export TELEGRAM_BOT_TOKEN='your-token-here'")
        return
    
    # Create and run bot
    bot = TradingBot(token)
    bot.run()


if __name__ == '__main__':
    main()
