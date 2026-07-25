import paramiko
import time

VPS_IP = "200.141.3.208"
VPS_USER = "root"
VPS_PASS = "mFYvxeWo-C+j&@M8"

def run_vps_command(ssh, cmd, timeout=300):
    print(f"\n==========================================")
    print(f"📌 Executing on VPS: {cmd[:100]}...")
    print(f"==========================================")
    stdin, stdout, stderr = ssh.exec_command(cmd, get_pty=True, timeout=timeout)
    
    for line in iter(stdout.readline, ""):
        print(line, end="")
        
    exit_status = stdout.channel.recv_exit_status()
    print(f"\n[Exit Code: {exit_status}]")
    return exit_status

def deploy():
    print(f"🚀 Connecting to Hostinger VPS at {VPS_IP} via SSH...")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        ssh.connect(hostname=VPS_IP, username=VPS_USER, password=VPS_PASS, timeout=30)
        print("✅ SSH Connection Successful!\n")
        
        # Combined Shell Deployment Script
        vps_script = """
set -e

echo "======================================================="
echo "🌟 STARTING FULL PRODUCTION AUTOMATED VPS INSTALLATION"
echo "======================================================="

export DEBIAN_FRONTEND=noninteractive

# 1. Update APT & Core Tools
echo "📦 1/6 Installing system prerequisites..."
apt-get update -y
apt-get install -y curl wget git build-essential software-properties-common nginx unzip python3-pip python3-venv

# 2. Install Node.js 20 & PM2
echo "⚡ 2/6 Installing Node.js 20 LTS & PM2..."
if ! command -v node &> /dev/null; then
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
    apt-get install -y nodejs
fi
npm install -g pm2

# 3. Install Google Chrome (for Playwright & Scraper)
echo "🌐 3/6 Installing Google Chrome Browser..."
if ! command -v google-chrome &> /dev/null; then
    wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
    dpkg -i google-chrome-stable_current_amd64.deb || apt-get install -f -y
    rm -f google-chrome-stable_current_amd64.deb
fi

# 4. Configure Backend Python Environment & .env
echo "🐍 4/6 Setting up Backend Python virtual environment..."
cd /root/reachmagnets/apps/backend

if [ ! -d "venv" ]; then
    python3 -m venv venv
fi
venv/bin/python -m pip install --upgrade pip
venv/bin/pip install -r requirements.txt
venv/bin/pip install playwright
venv/bin/playwright install-deps || true

if [ ! -f .env ]; then
    cp .env.example .env 2>/dev/null || touch .env
fi

if grep -q "ENABLE_AUTONOMOUS_SCHEDULER" .env; then
    sed -i 's/ENABLE_AUTONOMOUS_SCHEDULER=.*/ENABLE_AUTONOMOUS_SCHEDULER=True/' .env
else
    echo -e "\\nENABLE_AUTONOMOUS_SCHEDULER=True" >> .env
fi

# Verify database copy
if [ -f "/root/reachmagnets/reachmagnets.db" ] && [ ! -f "/root/reachmagnets/apps/backend/reachmagnets.db" ]; then
    cp /root/reachmagnets/reachmagnets.db /root/reachmagnets/apps/backend/reachmagnets.db
fi

# 5. Build Frontend Next.js Production App
echo "⚛️ 5/6 Building Frontend Next.js Production Bundle..."
cd /root/reachmagnets/apps/frontend
npm install
npm run build

# 6. PM2 Process Registration
echo "🚀 6/6 Launching Services in PM2..."
cd /root/reachmagnets
pm2 delete reachmagnets-backend reachmagnets-frontend 2>/dev/null || true

pm2 start "/root/reachmagnets/apps/backend/venv/bin/python" \\
    --name "reachmagnets-backend" \\
    -- -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2

pm2 start npm \\
    --name "reachmagnets-frontend" \\
    -- cwd "/root/reachmagnets/apps/frontend" \\
    -- start -- -p 3000

pm2 save
pm2 startup systemd -u root --hp /root || true

echo "======================================================="
echo "🎉 HOSTINGER VPS PRODUCTION DEPLOYMENT COMPLETE!"
echo "======================================================="
"""
        run_vps_command(ssh, vps_script, timeout=600)
        
        # Check final status
        print("\nVerifying Services & PM2 Status...")
        run_vps_command(ssh, "pm2 status")
        run_vps_command(ssh, "curl -s http://localhost:8000/health")
        run_vps_command(ssh, "curl -s -I http://localhost:3000 | head -n 5")

    except Exception as e:
        print(f"❌ Deployment Error: {e}")
    finally:
        ssh.close()
        print("\nSSH Session Closed.")

if __name__ == "__main__":
    deploy()
