"""
LangChain AI Agent for Super Gnosis
====================================

Intelligent orchestration agent using LangChain ReAct framework.

Key Features:
- ReAct (Reasoning + Acting) agent architecture
- Tool integration with Super Gnosis engines
- Multi-step reasoning for complex trading decisions
- Memory for context-aware decisions
- Conversation history tracking
- Custom tool definitions for:
  - Market data retrieval
  - Risk assessment
  - Portfolio analysis
  - Trade execution
  - Sentiment analysis

Agents Supported:
- ReAct Agent (default): Reason + Act in loops
- Function Calling Agent: Direct function invocation
- OpenAI Functions Agent: OpenAI-specific optimization
- Conversational Agent: Chat-based interaction

Installation:
    pip install langchain langchain-openai

Usage:
    # Basic agent
    agent = SuperGnosisAgent(api_key="sk-...")
    response = agent.run("Analyze BTC risk and suggest position size for $10k portfolio")
    
    # With custom tools
    agent = SuperGnosisAgent(api_key="sk-...", tools=[...])
    response = agent.run("What's the current gamma exposure for SPY options?")
    
    # Conversational mode
    agent = SuperGnosisAgent(api_key="sk-...", memory=True)
    response1 = agent.run("Analyze TSLA")
    response2 = agent.run("Now calculate hedge for that position")  # Remembers TSLA

Author: Super Gnosis Development Team
License: MIT
Version: 3.0.0
"""

from typing import List, Optional, Dict, Any, Callable
from langchain.agents import AgentType, initialize_agent, Tool
from langchain.memory import ConversationBufferMemory
from langchain_openai import ChatOpenAI
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain
from loguru import logger
import os
from dataclasses import dataclass
from datetime import datetime


@dataclass
class AgentResponse:
    """Agent response with metadata."""
    response: str
    reasoning: Optional[str]
    tools_used: List[str]
    timestamp: datetime
    token_usage: Optional[Dict[str, int]] = None


class SuperGnosisAgent:
    """
    LangChain-powered AI agent for intelligent trading orchestration.
    
    Uses ReAct (Reasoning + Acting) framework to:
    1. Reason about market conditions
    2. Select appropriate tools/engines
    3. Execute actions
    4. Reflect on results
    5. Iterate until goal achieved
    
    Integrates with Super Gnosis engines for:
    - Risk assessment (Hedge Engine)
    - Liquidity analysis (Liquidity Engine)
    - Sentiment evaluation (Sentiment Engine)
    - Trade execution (Trade Agent, Execution Engine)
    - Portfolio optimization (Composer)
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gpt-4-turbo-preview",
        temperature: float = 0.7,
        memory: bool = True,
        agent_type: AgentType = AgentType.ZERO_SHOT_REACT_DESCRIPTION,
        tools: Optional[List[Tool]] = None,
        verbose: bool = False,
        max_iterations: int = 10
    ):
        """
        Initialize SuperGnosis AI Agent.
        
        Args:
            api_key: OpenAI API key (or set OPENAI_API_KEY env var)
            model: LLM model to use (gpt-4-turbo-preview, gpt-3.5-turbo, etc.)
            temperature: Creativity level (0=deterministic, 1=creative)
            memory: Enable conversation memory
            agent_type: LangChain agent type
            tools: Custom tools (auto-generated if None)
            verbose: Enable detailed logging
            max_iterations: Maximum reasoning iterations
        """
        # Set API key
        if api_key:
            os.environ['OPENAI_API_KEY'] = api_key
        elif not os.getenv('OPENAI_API_KEY'):
            raise ValueError("OpenAI API key required (pass api_key or set OPENAI_API_KEY env var)")
        
        self.model = model
        self.temperature = temperature
        self.verbose = verbose
        self.max_iterations = max_iterations
        
        # Initialize LLM
        self.llm = ChatOpenAI(
            model=model,
            temperature=temperature,
            verbose=verbose
        )
        
        # Initialize memory if enabled
        self.memory = None
        if memory:
            self.memory = ConversationBufferMemory(
                memory_key="chat_history",
                return_messages=True
            )
        
        # Get tools
        self.tools = tools if tools else self._create_default_tools()
        
        # Initialize agent
        self.agent = initialize_agent(
            tools=self.tools,
            llm=self.llm,
            agent=agent_type,
            verbose=verbose,
            memory=self.memory,
            max_iterations=max_iterations,
            handle_parsing_errors=True
        )
        
        logger.info(f"✅ SuperGnosis AI Agent initialized")
        logger.info(f"   Model: {model}")
        logger.info(f"   Tools: {len(self.tools)} available")
        logger.info(f"   Memory: {'enabled' if memory else 'disabled'}")
    
    def run(
        self,
        query: str,
        context: Optional[Dict[str, Any]] = None
    ) -> AgentResponse:
        """
        Run agent with a query.
        
        Args:
            query: User question or command
            context: Additional context (portfolio, market data, etc.)
        
        Returns:
            AgentResponse with reasoning and result
        """
        try:
            # Add context to query if provided
            if context:
                context_str = "\n".join([f"{k}: {v}" for k, v in context.items()])
                full_query = f"{query}\n\nContext:\n{context_str}"
            else:
                full_query = query
            
            # Run agent
            logger.debug(f"🤖 Agent processing: {query}")
            result = self.agent.invoke({"input": full_query})
            
            # Extract tools used from intermediate steps
            tools_used = []
            if 'intermediate_steps' in result:
                for step in result['intermediate_steps']:
                    if hasattr(step[0], 'tool'):
                        tools_used.append(step[0].tool)
            
            response = AgentResponse(
                response=result['output'],
                reasoning=None,  # LangChain doesn't expose reasoning directly
                tools_used=tools_used,
                timestamp=datetime.now()
            )
            
            logger.info(f"✅ Agent completed (tools used: {len(tools_used)})")
            return response
            
        except Exception as e:
            logger.error(f"❌ Agent error: {e}")
            raise
    
    def run_async(self, query: str) -> str:
        """Run agent asynchronously (for background tasks)."""
        return self.run(query).response
    
    def clear_memory(self):
        """Clear conversation memory."""
        if self.memory:
            self.memory.clear()
            logger.info("🧹 Agent memory cleared")
    
    def add_tool(self, tool: Tool):
        """Add a new tool to the agent."""
        self.tools.append(tool)
        # Reinitialize agent with new tools
        self.agent = initialize_agent(
            tools=self.tools,
            llm=self.llm,
            agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION,
            verbose=self.verbose,
            memory=self.memory,
            max_iterations=self.max_iterations
        )
        logger.info(f"➕ Added tool: {tool.name}")
    
    def _create_default_tools(self) -> List[Tool]:
        """
        Create default Super Gnosis tools.
        
        These are stub implementations - replace with actual engine calls.
        """
        tools = [
            Tool(
                name="Market Data",
                func=self._get_market_data,
                description="Get current market data for a symbol (price, volume, etc.). Input: symbol (e.g., 'AAPL', 'BTC/USD')"
            ),
            Tool(
                name="Risk Analysis",
                func=self._analyze_risk,
                description="Analyze risk metrics for a position (Greeks, VaR, max drawdown). Input: symbol and position size"
            ),
            Tool(
                name="Liquidity Check",
                func=self._check_liquidity,
                description="Check liquidity for a symbol (bid-ask spread, depth, impact). Input: symbol"
            ),
            Tool(
                name="Sentiment Analysis",
                func=self._analyze_sentiment,
                description="Analyze market sentiment for a symbol (news, social, technical). Input: symbol"
            ),
            Tool(
                name="Portfolio Analysis",
                func=self._analyze_portfolio,
                description="Analyze current portfolio (allocation, risk, performance). Input: 'current' or portfolio dict"
            ),
            Tool(
                name="Position Sizing",
                func=self._calculate_position_size,
                description="Calculate optimal position size based on risk (Kelly, fixed fractional). Input: symbol, portfolio value, risk tolerance"
            ),
            Tool(
                name="Options Greeks",
                func=self._get_options_greeks,
                description="Calculate option Greeks (delta, gamma, vega, theta). Input: option details (spot, strike, expiry, vol, type)"
            ),
            Tool(
                name="Execute Trade",
                func=self._execute_trade,
                description="Execute a trade (paper trading by default). Input: symbol, side (buy/sell), quantity, order type"
            )
        ]
        
        return tools
    
    # ========================================================================
    # TOOL IMPLEMENTATIONS (Stubs - Replace with actual engine calls)
    # ========================================================================
    
    def _get_market_data(self, symbol: str) -> str:
        """Get market data for a symbol."""
        # TODO: Replace with actual DataStore call
        return f"Market data for {symbol}: Price $150.00, Volume 1.2M, Change +2.5%"
    
    def _analyze_risk(self, query: str) -> str:
        """Analyze risk for a position."""
        # TODO: Replace with actual Hedge Engine call
        return f"Risk analysis for {query}: Delta 0.65, Gamma 0.03, VaR $1,200 (95%)"
    
    def _check_liquidity(self, symbol: str) -> str:
        """Check liquidity for a symbol."""
        # TODO: Replace with actual Liquidity Engine call
        return f"Liquidity for {symbol}: Bid-ask spread 0.05%, Depth $500k at 0.1%, Impact LOW"
    
    def _analyze_sentiment(self, symbol: str) -> str:
        """Analyze sentiment for a symbol."""
        # TODO: Replace with actual Sentiment Engine call
        return f"Sentiment for {symbol}: Positive (0.72), News: 15 articles (80% positive), Social: Bullish trend"
    
    def _analyze_portfolio(self, portfolio_input: str) -> str:
        """Analyze portfolio."""
        # TODO: Replace with actual Composer call
        return f"Portfolio analysis: Total value $50k, Risk score 6.5/10, Sharpe 1.8, Max drawdown -12%"
    
    def _calculate_position_size(self, query: str) -> str:
        """Calculate position size."""
        # TODO: Replace with actual risk calculation
        return f"Position sizing for {query}: Recommended size: 50 shares ($7,500), Risk: 2% of portfolio"
    
    def _get_options_greeks(self, query: str) -> str:
        """Get option Greeks."""
        # TODO: Replace with actual Hedge Engine vollib call
        return f"Option Greeks for {query}: Delta 0.65, Gamma 0.03, Vega 0.15, Theta -0.05"
    
    def _execute_trade(self, query: str) -> str:
        """Execute trade."""
        # TODO: Replace with actual Execution Engine call
        return f"Trade executed: {query} (Paper trading). Order ID: TEST123, Status: Filled"


# ============================================================================
# SPECIALIZED AGENTS
# ============================================================================

class RiskAgent(SuperGnosisAgent):
    """Specialized agent for risk management."""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.system_prompt = """You are a risk management expert for a quantitative trading system.
Your primary goal is to assess and minimize risk while maximizing risk-adjusted returns.
Always consider: position sizing, portfolio correlation, tail risk, and liquidity constraints."""


class TradingAgent(SuperGnosisAgent):
    """Specialized agent for trade execution."""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.system_prompt = """You are a trade execution specialist.
Your goal is to execute trades with minimal market impact and optimal timing.
Consider: liquidity, spread, time-of-day effects, and order types."""


class PortfolioAgent(SuperGnosisAgent):
    """Specialized agent for portfolio management."""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.system_prompt = """You are a portfolio manager using dynamic hedging physics.
Your goal is to optimize portfolio allocation while managing energy states and risk.
Consider: diversification, correlation, rebalancing, and tax efficiency."""


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

def create_default_agent(
    api_key: Optional[str] = None,
    verbose: bool = False
) -> SuperGnosisAgent:
    """
    Create default SuperGnosis agent with standard configuration.
    
    Args:
        api_key: OpenAI API key
        verbose: Enable detailed logging
    
    Returns:
        Configured SuperGnosisAgent
    """
    return SuperGnosisAgent(
        api_key=api_key,
        model="gpt-4-turbo-preview",
        temperature=0.7,
        memory=True,
        verbose=verbose
    )


def create_risk_agent(
    api_key: Optional[str] = None,
    verbose: bool = False
) -> RiskAgent:
    """Create specialized risk management agent."""
    return RiskAgent(
        api_key=api_key,
        model="gpt-4-turbo-preview",
        temperature=0.3,  # More conservative for risk
        verbose=verbose
    )


def create_trading_agent(
    api_key: Optional[str] = None,
    verbose: bool = False
) -> TradingAgent:
    """Create specialized trading execution agent."""
    return TradingAgent(
        api_key=api_key,
        model="gpt-4-turbo-preview",
        temperature=0.5,
        verbose=verbose
    )


# ============================================================================
# EXAMPLE USAGE
# ============================================================================

if __name__ == "__main__":
    import sys
    
    # Check for API key
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("⚠️  OPENAI_API_KEY not set. Set it to run examples:")
        print("   export OPENAI_API_KEY='sk-...'")
        sys.exit(1)
    
    print("\n🤖 SuperGnosis AI Agent Examples\n")
    
    # Example 1: Basic query
    print("Example 1: Basic market analysis")
    agent = create_default_agent(verbose=False)
    response = agent.run("Analyze AAPL and suggest if I should buy or sell")
    print(f"Response: {response.response}")
    print(f"Tools used: {response.tools_used}")
    
    # Example 2: Risk analysis
    print("\n\nExample 2: Risk analysis")
    risk_agent = create_risk_agent(verbose=False)
    response = risk_agent.run(
        "Analyze risk for a $10,000 position in TSLA",
        context={"portfolio_value": 50000, "risk_tolerance": "moderate"}
    )
    print(f"Response: {response.response}")
    
    # Example 3: Conversational mode
    print("\n\nExample 3: Conversational mode (with memory)")
    agent = create_default_agent(verbose=False)
    
    response1 = agent.run("What's the current price of BTC?")
    print(f"Query 1: {response1.response}")
    
    response2 = agent.run("Now calculate risk for a $5k position")  # Remembers BTC
    print(f"Query 2: {response2.response}")
    
    # Example 4: Portfolio optimization
    print("\n\nExample 4: Portfolio optimization")
    portfolio_agent = PortfolioAgent(verbose=False)
    response = portfolio_agent.run(
        "Optimize my portfolio for maximum Sharpe ratio",
        context={
            "holdings": {"AAPL": 100, "GOOGL": 50, "SPY": 200},
            "cash": 10000,
            "target_risk": 0.15
        }
    )
    print(f"Response: {response.response}")
    
    print("\n\n✅ AI Agent examples complete!")
    print("   Ready for intelligent trading orchestration")
