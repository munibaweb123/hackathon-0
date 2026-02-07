#!/bin/bash
# Startup script for Personal AI Employee using uv

echo "Starting Personal AI Employee with uv..."
echo "Make sure you have placed files in the obsidian-vault/inbox/ folder for processing"
echo ""

# Run the AI Employee
uv run python -c "
from src.ai_employee import AIEmployee
import signal
import sys
import time

def signal_handler(sig, frame):
    print('\\nShutting down AI Employee gracefully...')
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)

print('🚀 Starting Personal AI Employee...')
print('📁 Vault path: ./obsidian-vault')
print('🔄 Monitoring for new files in inbox folder...')
print('🔐 Bronze Tier security enforced')
print('📋 Human approval workflows active')
print('📜 Audit logging enabled')
print('')
print('Press Ctrl+C to stop the AI Employee')
print('')

# Create AI Employee instance
ai_employee = AIEmployee()

# Start monitoring
ai_employee.start_monitoring()

try:
    print('✅ AI Employee is now monitoring for files...')
    print('')
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    print('\\n🛑 Stopping AI Employee...')
finally:
    ai_employee.stop_monitoring()
    print('👋 AI Employee stopped. Goodbye!')
"