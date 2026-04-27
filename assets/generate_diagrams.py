#!/usr/bin/env python3
"""Generate professional architecture diagrams for PhantomStrike."""

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, Rectangle, FancyArrowPatch
import numpy as np

# Set style
plt.style.use('dark_background')


def create_architecture_diagram():
    """Create system architecture diagram."""
    fig, ax = plt.subplots(1, 1, figsize=(14, 10))
    ax.set_xlim(0, 14)
    ax.set_ylim(0, 10)
    ax.axis('off')
    
    # Title
    ax.text(7, 9.5, 'PHANTOMSTRIKE v2.0 ARCHITECTURE', 
            fontsize=18, fontweight='bold', ha='center', color='#FF6B00')
    
    # Colors
    colors = {
        'frontend': '#1E3A5F',
        'api': '#0D4F3C',
        'core': '#4A1C4A',
        'module': '#2D1B4E',
        'ai': '#8B4513',
        'border': '#FF6B00'
    }
    
    # Frontend Layer
    frontend_box = FancyBboxPatch((0.5, 7.5), 13, 1.5, 
                                   boxstyle="round,pad=0.05", 
                                   facecolor=colors['frontend'], 
                                   edgecolor=colors['border'], linewidth=2)
    ax.add_patch(frontend_box)
    ax.text(7, 8.8, 'FRONTEND LAYER', fontsize=11, fontweight='bold', ha='center', color='white')
    ax.text(3, 8.2, 'Web Dashboard', fontsize=9, ha='center', color='#00D4AA')
    ax.text(7, 8.2, 'WebSocket', fontsize=9, ha='center', color='#00D4AA')
    ax.text(11, 8.2, 'CLI (Rich/TUI)', fontsize=9, ha='center', color='#00D4AA')
    
    # API Layer
    api_box = FancyBboxPatch((0.5, 5.5), 13, 1.5,
                              boxstyle="round,pad=0.05",
                              facecolor=colors['api'],
                              edgecolor=colors['border'], linewidth=2)
    ax.add_patch(api_box)
    ax.text(7, 6.8, 'API LAYER (FastAPI)', fontsize=11, fontweight='bold', ha='center', color='white')
    endpoints = ['/api/scan', '/api/ai', '/api/payload', '/ws', '/health']
    for i, ep in enumerate(endpoints):
        x_pos = 2 + i * 2.5
        ax.text(x_pos, 6.2, ep, fontsize=8, ha='center', color='#00FF88')
    
    # Core Engine
    core_box = FancyBboxPatch((0.5, 3.5), 13, 1.5,
                               boxstyle="round,pad=0.05",
                               facecolor=colors['core'],
                               edgecolor=colors['border'], linewidth=2)
    ax.add_patch(core_box)
    ax.text(7, 4.8, 'CORE ENGINE (Async Python)', fontsize=11, fontweight='bold', ha='center', color='white')
    core_components = ['EventBus', 'ModuleLoader', 'AI Engine', 'ScanLock']
    for i, comp in enumerate(core_components):
        x_pos = 2.5 + i * 3
        ax.text(x_pos, 4.2, comp, fontsize=9, ha='center', color='#FF6B9D')
    
    # Modules
    module_box = FancyBboxPatch((0.5, 1.5), 9, 1.5,
                                 boxstyle="round,pad=0.05",
                                 facecolor=colors['module'],
                                 edgecolor=colors['border'], linewidth=2)
    ax.add_patch(module_box)
    ax.text(5, 2.8, 'MODULES (11 Total)', fontsize=10, fontweight='bold', ha='center', color='white')
    modules = ['OSINT', 'Network', 'Web', 'Cloud', 'Identity', 'Cred', 'Stealth', 'Exploit', 'C2', 'Post', 'Report']
    for i, mod in enumerate(modules[:6]):
        ax.text(1.5 + i * 1.5, 2.2, mod, fontsize=7, ha='center', color='#C084FC')
    for i, mod in enumerate(modules[6:]):
        ax.text(1.5 + i * 1.5, 1.8, mod, fontsize=7, ha='center', color='#C084FC')
    
    # AI Engine
    ai_box = FancyBboxPatch((10, 1.5), 3.5, 1.5,
                             boxstyle="round,pad=0.05",
                             facecolor=colors['ai'],
                             edgecolor=colors['border'], linewidth=2)
    ax.add_patch(ai_box)
    ax.text(11.75, 2.8, 'AI ENGINE', fontsize=10, fontweight='bold', ha='center', color='white')
    ax.text(11.75, 2.2, 'Groq•OpenRouter', fontsize=8, ha='center', color='#FFD700')
    ax.text(11.75, 1.8, 'Gemini•Cerebras', fontsize=8, ha='center', color='#FFD700')
    
    # Arrows
    arrow_props = dict(arrowstyle='->', color='#FF6B00', lw=2)
    ax.annotate('', xy=(7, 7.5), xytext=(7, 9), arrowprops=arrow_props)
    ax.annotate('', xy=(7, 5.5), xytext=(7, 7.5), arrowprops=arrow_props)
    ax.annotate('', xy=(7, 3.5), xytext=(7, 5.5), arrowprops=arrow_props)
    ax.annotate('', xy=(5, 3), xytext=(5, 3.5), arrowprops=arrow_props)
    ax.annotate('', xy=(11.75, 3), xytext=(11.75, 3.5), arrowprops=arrow_props)
    
    plt.tight_layout()
    plt.savefig('architecture_diagram.png', dpi=150, bbox_inches='tight', 
                facecolor='#0D1117', edgecolor='none')
    plt.close()
    print("✅ Created architecture_diagram.png")


def create_killchain_diagram():
    """Create kill chain flow diagram."""
    fig, ax = plt.subplots(1, 1, figsize=(14, 6))
    ax.set_xlim(0, 14)
    ax.set_ylim(0, 6)
    ax.axis('off')
    
    # Title
    ax.text(7, 5.5, 'MITRE ATT&CK KILL CHAIN', 
            fontsize=16, fontweight='bold', ha='center', color='#FF6B00')
    
    phases = [
        ('RECON', '#1E3A5F', ['OSINT', 'Network', 'Web Crawl']),
        ('WEAPONIZE', '#8B4513', ['AI Analysis', 'Payload Gen']),
        ('DELIVER', '#4A1C4A', ['Exploit', 'C2 Deploy']),
        ('EXPLOIT', '#0D4F3C', ['Execute', 'PrivEsc']),
        ('INSTALL', '#2D1B4E', ['Persistence', 'Backdoor']),
        ('CONTROL', '#1E3A5F', ['C2 Channel', 'Exfil']),
    ]
    
    box_width = 2
    box_height = 1.2
    start_x = 0.5
    spacing = 2.3
    
    for i, (phase, color, actions) in enumerate(phases):
        x = start_x + i * spacing
        y = 3
        
        # Phase box
        box = FancyBboxPatch((x, y), box_width, box_height,
                              boxstyle="round,pad=0.05",
                              facecolor=color, edgecolor='#FF6B00', linewidth=2)
        ax.add_patch(box)
        
        # Phase name
        ax.text(x + box_width/2, y + box_height - 0.2, phase, 
                fontsize=9, fontweight='bold', ha='center', color='white')
        
        # Actions
        for j, action in enumerate(actions):
            ax.text(x + box_width/2, y + box_height - 0.5 - j*0.25, action,
                    fontsize=7, ha='center', color='#00D4AA')
        
        # Arrow to next
        if i < len(phases) - 1:
            ax.annotate('', xy=(x + box_width + 0.1, y + box_height/2),
                       xytext=(x + box_width - 0.1, y + box_height/2),
                       arrowprops=dict(arrowstyle='->', color='#FF6B00', lw=2))
    
    # Add target input arrow
    ax.annotate('', xy=(start_x + box_width/2, 5), xytext=(start_x + box_width/2, 5.2),
               arrowprops=dict(arrowstyle='->', color='#FF6B00', lw=2))
    ax.text(start_x + box_width/2, 5.3, 'TARGET INPUT', fontsize=9, ha='center', color='#FFD700')
    
    # Add report output
    last_x = start_x + (len(phases)-1) * spacing
    ax.annotate('', xy=(last_x + box_width/2, 2.8), xytext=(last_x + box_width/2, 2.6),
               arrowprops=dict(arrowstyle='->', color='#FF6B00', lw=2))
    ax.text(last_x + box_width/2, 2.4, 'REPORT', fontsize=9, ha='center', color='#FFD700')
    
    plt.tight_layout()
    plt.savefig('killchain_diagram.png', dpi=150, bbox_inches='tight',
                facecolor='#0D1117', edgecolor='none')
    plt.close()
    print("✅ Created killchain_diagram.png")


def create_modules_diagram():
    """Create modules overview diagram."""
    fig, ax = plt.subplots(1, 1, figsize=(12, 8))
    ax.set_xlim(0, 12)
    ax.set_ylim(0, 8)
    ax.axis('off')
    
    # Title
    ax.text(6, 7.5, 'PHANTOMSTRIKE MODULES', 
            fontsize=16, fontweight='bold', ha='center', color='#FF6B00')
    ax.text(6, 7.1, '11 Offensive Security Modules', 
            fontsize=11, ha='center', color='#888888')
    
    modules = [
        ('phantom-osint', 'RECON', '#1E3A5F', 'Subdomains, Emails, DNS'),
        ('phantom-network', 'RECON', '#1E3A5F', 'Port Scan, Services'),
        ('phantom-web', 'VULN', '#4A1C4A', 'SQLi, XSS, CSRF, XXE'),
        ('phantom-cloud', 'VULN', '#4A1C4A', 'AWS/Azure/GCP Scan'),
        ('phantom-identity', 'VULN', '#4A1C4A', 'JWT, OAuth Attacks'),
        ('phantom-cred', 'VULN', '#4A1C4A', 'Brute Force, Spraying'),
        ('phantom-stealth', 'EVASION', '#8B4513', 'WAF Bypass, AV Evasion'),
        ('phantom-exploit', 'EXPLOIT', '#0D4F3C', 'Auto-Exploitation'),
        ('phantom-c2', 'C2', '#2D1B4E', 'Agent Management'),
        ('phantom-post', 'POST', '#1E3A5F', 'PrivEsc, Lateral'),
        ('phantom-report', 'REPORT', '#1E3A5F', 'MITRE Mapping'),
    ]
    
    # Draw module boxes in grid
    for i, (name, phase, color, desc) in enumerate(modules):
        row = i // 3
        col = i % 3
        x = 1 + col * 3.5
        y = 5.5 - row * 1.8
        
        # Box
        box = FancyBboxPatch((x, y), 3, 1.4,
                              boxstyle="round,pad=0.05",
                              facecolor=color, edgecolor='#FF6B00', linewidth=1.5)
        ax.add_patch(box)
        
        # Module name
        ax.text(x + 1.5, y + 1.1, name, fontsize=8, fontweight='bold', 
                ha='center', color='white')
        
        # Phase badge
        phase_color = {'RECON': '#00D4AA', 'VULN': '#FF6B6B', 'EVASION': '#FFD700',
                       'EXPLOIT': '#FF6B00', 'C2': '#C084FC', 'POST': '#4ECDC4',
                       'REPORT': '#95E1D3'}[phase]
        ax.text(x + 1.5, y + 0.75, phase, fontsize=7, ha='center', 
                color=phase_color, fontweight='bold')
        
        # Description
        ax.text(x + 1.5, y + 0.35, desc, fontsize=6, ha='center', color='#AAAAAA')
    
    plt.tight_layout()
    plt.savefig('modules_diagram.png', dpi=150, bbox_inches='tight',
                facecolor='#0D1117', edgecolor='none')
    plt.close()
    print("✅ Created modules_diagram.png")


if __name__ == '__main__':
    print("🎨 Generating PhantomStrike Architecture Diagrams...")
    print("=" * 50)
    
    create_architecture_diagram()
    create_killchain_diagram()
    create_modules_diagram()
    
    print("=" * 50)
    print("✅ All diagrams generated successfully!")
    print("\nFiles created:")
    print("  - assets/architecture_diagram.png")
    print("  - assets/killchain_diagram.png")
    print("  - assets/modules_diagram.png")
