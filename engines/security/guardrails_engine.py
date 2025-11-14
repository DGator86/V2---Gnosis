"""
Security guardrails engine
Implements PII redaction, safe tool execution, and input validation
Based on Marktechpost Security and Guardrails patterns
"""
import re
from datetime import datetime
from typing import Dict, Any, List, Optional, Callable
from ..orchestration.logger import get_logger

logger = get_logger(__name__)


class GuardrailsEngine:
    """Engine for security and safety checks"""
    
    # PII patterns
    PII_PATTERNS = {
        'ssn': re.compile(r'\b\d{3}-\d{2}-\d{4}\b'),
        'email': re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'),
        'phone': re.compile(r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b'),
        'credit_card': re.compile(r'\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b'),
        'api_key': re.compile(r'(?i)(api[_-]?key|apikey|token)["\s:=]+([a-zA-Z0-9_\-]{20,})'),
    }
    
    # Dangerous code patterns
    DANGEROUS_PATTERNS = [
        r'exec\s*\(',
        r'eval\s*\(',
        r'__import__\s*\(',
        r'compile\s*\(',
        r'open\s*\(',
        r'os\.system',
        r'subprocess\.',
        r'rm\s+-rf',
    ]
    
    def __init__(self, 
                 enable_pii_redaction: bool = True,
                 enable_code_validation: bool = True,
                 max_tool_timeout: int = 30,
                 allowed_tools: Optional[List[str]] = None,
                 blocked_patterns: Optional[List[str]] = None):
        """
        Args:
            enable_pii_redaction: Enable PII detection and redaction
            enable_code_validation: Enable dangerous code pattern detection
            max_tool_timeout: Maximum seconds for tool execution
            allowed_tools: List of allowed tool names (None = all allowed)
            blocked_patterns: Additional patterns to block
        """
        self.enable_pii_redaction = enable_pii_redaction
        self.enable_code_validation = enable_code_validation
        self.max_tool_timeout = max_tool_timeout
        self.allowed_tools = set(allowed_tools) if allowed_tools else None
        
        self.blocked_patterns = self.DANGEROUS_PATTERNS.copy()
        if blocked_patterns:
            self.blocked_patterns.extend(blocked_patterns)
        
        logger.info(f"Guardrails engine initialized: pii={enable_pii_redaction}, "
                   f"code_val={enable_code_validation}, timeout={max_tool_timeout}s")
    
    def redact_pii(self, text: str) -> str:
        """Redact PII from text"""
        if not self.enable_pii_redaction:
            return text
        
        redacted = text
        redaction_count = 0
        
        for pii_type, pattern in self.PII_PATTERNS.items():
            matches = pattern.findall(redacted)
            if matches:
                redacted = pattern.sub(f'[REDACTED_{pii_type.upper()}]', redacted)
                redaction_count += len(matches)
        
        if redaction_count > 0:
            logger.warning(f"Redacted {redaction_count} PII instances from text")
        
        return redacted
    
    def validate_code(self, code: str) -> Dict[str, Any]:
        """
        Validate code for dangerous patterns
        Returns dict with 'safe' bool and 'issues' list
        """
        if not self.enable_code_validation:
            return {"safe": True, "issues": []}
        
        issues = []
        
        for pattern in self.blocked_patterns:
            if re.search(pattern, code, re.IGNORECASE):
                issues.append(f"Dangerous pattern detected: {pattern}")
        
        safe = len(issues) == 0
        
        if not safe:
            logger.warning(f"Code validation failed: {len(issues)} issues")
        
        return {"safe": safe, "issues": issues}
    
    def validate_tool_call(self, tool_name: str, tool_args: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate tool call before execution
        Returns dict with 'allowed' bool and 'reason' string
        """
        # Check if tool is in allowed list
        if self.allowed_tools and tool_name not in self.allowed_tools:
            return {
                "allowed": False,
                "reason": f"Tool '{tool_name}' not in allowed list"
            }
        
        # Validate tool arguments for PII
        args_str = str(tool_args)
        
        if self.enable_pii_redaction:
            for pii_type, pattern in self.PII_PATTERNS.items():
                if pattern.search(args_str):
                    return {
                        "allowed": False,
                        "reason": f"PII detected in tool arguments: {pii_type}"
                    }
        
        # Validate for dangerous patterns
        if self.enable_code_validation:
            validation = self.validate_code(args_str)
            if not validation["safe"]:
                return {
                    "allowed": False,
                    "reason": f"Dangerous patterns in tool args: {validation['issues']}"
                }
        
        return {"allowed": True, "reason": "passed"}
    
    def safe_tool_call(self, 
                      tool_name: str, 
                      tool_fn: Callable,
                      tool_args: Dict[str, Any],
                      timeout: Optional[int] = None) -> Dict[str, Any]:
        """
        Execute tool with safety checks
        
        Returns dict with:
            - success: bool
            - output: Any (if success)
            - error: str (if failed)
            - blocked: bool (if blocked by guardrails)
        """
        # Validate tool call
        validation = self.validate_tool_call(tool_name, tool_args)
        
        if not validation["allowed"]:
            logger.warning(f"Tool call blocked: {tool_name} - {validation['reason']}")
            return {
                "success": False,
                "error": validation["reason"],
                "blocked": True
            }
        
        # Execute with timeout
        timeout = timeout or self.max_tool_timeout
        
        try:
            # Note: Real timeout requires threading/multiprocessing
            # This is a simplified version
            output = tool_fn(**tool_args)
            
            # Redact PII from output if string
            if isinstance(output, str):
                output = self.redact_pii(output)
            
            return {
                "success": True,
                "output": output,
                "blocked": False
            }
            
        except Exception as e:
            logger.error(f"Tool execution failed: {tool_name} - {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "blocked": False
            }
    
    def audit_log(self, 
                  action: str,
                  actor: str,
                  details: Dict[str, Any],
                  risk_level: str = "low") -> Dict[str, Any]:
        """
        Create audit log entry
        For self-auditing guardrails
        """
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "action": action,
            "actor": actor,
            "risk_level": risk_level,
            "details": details
        }
        
        if risk_level in ["high", "critical"]:
            logger.warning(f"High-risk action logged: {action} by {actor}")
        
        return log_entry
