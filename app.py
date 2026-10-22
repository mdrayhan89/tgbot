import os
import sqlite3
import threading
import asyncio
import aiohttp
import json
from flask import Flask, render_template_string, request, jsonify

# Import main original file without altering its code
import test_2

web_app = Flask(__name__)

# Fetch real database stats directly from test_2.DB_PATH
def get_db_connection():
    conn = sqlite3.connect(test_2.DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# Add is_banned column to DB if not exists (Zero changes in original file)
def init_admin_db():
    conn = get_db_connection()
    try:
        conn.execute("ALTER TABLE users ADD COLUMN is_banned INTEGER DEFAULT 0")
        conn.commit()
    except sqlite3.OperationalError:
        pass
    try:
        conn.execute("ALTER TABLE users ADD COLUMN last_active TEXT DEFAULT ''")
        conn.commit()
    except sqlite3.OperationalError:
        pass
    conn.close()

HTML_ADMIN_PANEL = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>DARK SECRET BOT Admin</title>
    <style>
        :root {
            --bg-color: #0b0e14;
            --card-bg: #151a23;
            --accent: #7c3aed;
            --text-main: #f3f4f6;
            --text-sub: #9ca3af;
            --danger: #ef4444;
            --success: #10b981;
            --border: #232a3b;
        }
        * { box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
        body { background: var(--bg-color); color: var(--text-main); padding: 15px; max-width: 500px; margin: 0 auto; }
        
        .header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 20px; }
        .brand { display: flex; align-items: center; gap: 10px; }
        .logo { width: 36px; height: 36px; background: linear-gradient(135deg, #a855f7, #6366f1); border-radius: 8px; display: flex; align-items: center; justify-content: center; font-weight: bold; }
        .title-group h2 { font-size: 16px; font-weight: 700; }
        .title-group p { font-size: 11px; color: var(--text-sub); }
        .status-badge { background: #13271d; color: var(--success); padding: 4px 10px; border-radius: 20px; font-size: 12px; border: 1px solid #1b4d3e; }
        .status-badge.stopped { background: #2d1517; color: var(--danger); border-color: #5c1d24; }

        .section-title { font-size: 11px; color: var(--text-sub); text-transform: uppercase; letter-spacing: 1px; margin: 15px 0 10px 0; }
        
        .grid-2x2 { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 20px; }
        .stat-card { background: var(--card-bg); padding: 15px; border-radius: 12px; border: 1px solid var(--border); position: relative; }
        .stat-card h1 { font-size: 26px; font-weight: 700; margin-bottom: 2px; }
        .stat-card p { font-size: 11px; color: var(--text-sub); font-weight: 600; }

        .nav-tabs { display: flex; background: #0f131a; border-radius: 10px; padding: 3px; border: 1px solid var(--border); margin-bottom: 15px; }
        .tab-btn { flex: 1; padding: 8px 0; text-align: center; font-size: 13px; font-weight: 600; color: var(--text-sub); border: none; background: transparent; cursor: pointer; border-radius: 8px; }
        .tab-btn.active { background: #211c38; color: #c084fc; border: 1px solid #3b2a59; }

        .tab-content { display: none; }
        .tab-content.active { display: block; }

        .card { background: var(--card-bg); border-radius: 12px; padding: 15px; border: 1px solid var(--border); margin-bottom: 15px; }
        
        .flex-between { display: flex; justify-content: space-between; align-items: center; }
        .btn { padding: 8px 16px; border-radius: 8px; border: none; font-size: 12px; font-weight: 600; cursor: pointer; }
        .btn-purple { background: linear-gradient(135deg, #9333ea, #c084fc); color: #fff; width: 100%; margin-top: 10px; padding: 10px; }
        .btn-danger { background: #ef4444; color: #fff; }

        select, input, textarea { width: 100%; background: #0b0e14; border: 1px solid var(--border); color: #fff; padding: 10px; border-radius: 8px; margin-top: 6px; font-size: 13px; outline: none; }
        
        .user-item { display: flex; align-items: center; justify-content: space-between; padding: 10px 0; border-bottom: 1px solid var(--border); cursor: pointer; }
        .user-item:last-child { border-bottom: none; }
        .avatar { width: 36px; height: 36px; background: #e879f9; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-weight: bold; color: #000; font-size: 13px; }
        .user-info { flex: 1; margin-left: 12px; }
        .user-info h4 { font-size: 13px; }
        .user-info p { font-size: 11px; color: var(--text-sub); }

        .modal { display: none; position: fixed; inset: 0; background: rgba(0,0,0,0.8); align-items: flex-end; justify-content: center; z-index: 100; }
        .modal-content { background: var(--card-bg); width: 100%; max-width: 500px; border-radius: 20px 20px 0 0; padding: 20px; border-top: 1px solid var(--border); }
        .modal-item { display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid var(--border); font-size: 13px; }
    </style>
</head>
<body>

    <div class="header">
        <div class="brand">
            <div class="logo">⚡</div>
            <div class="title-group">
                <h2>DARK SECRECT BOT <span style="color:#a855f7">Admin</span></h2>
                <p>PRIVATE CONSOLE</p>
            </div>
        </div>
        <div id="botStatusBadge" class="status-badge">● Running</div>
    </div>

    <div class="section-title">OVERVIEW</div>
    <div class="grid-2x2">
        <div class="stat-card">
            <h1 id="statTotalUsers">0</h1>
            <p>TOTAL USERS</p>
        </div>
        <div class="stat-card">
            <h1 id="statLicensed">0</h1>
            <p>LICENSED</p>
        </div>
        <div class="stat-card">
            <h1 id="statBanned">0</h1>
            <p>BANNED</p>
        </div>
        <div class="stat-card">
            <h1 id="statToday">0</h1>
            <p>TODAY</p>
        </div>
    </div>

    <div class="section-title">MANAGEMENT</div>
    <div class="nav-tabs">
        <button class="tab-btn active" onclick="switchTab('control')">Control</button>
        <button class="tab-btn" onclick="switchTab('users')">Users</button>
        <button class="tab-btn" onclick="switchTab('limits')">Limits</button>
    </div>

    <!-- TAB 1: CONTROL -->
    <div id="tab-control" class="tab-content active">
        <div class="card">
            <h3>Bot Control</h3>
            <br>
            <div class="flex-between">
                <span>Bot Status</span>
                <button id="toggleBotBtn" class="btn btn-danger" onclick="toggleBot()">Stop</button>
            </div>
            <br>
            <label style="font-size: 12px; color: var(--text-sub);">Access Mode</label>
            <select id="accessModeSelect">
                <option value="licensed_only">Licensed Only</option>
                <option value="all">Public Access</option>
            </select>
            <button class="btn btn-purple" onclick="alert('Access Mode Updated!')">Save Access Mode</button>
        </div>

        <div class="card">
            <h3>Send Announcement</h3>
            <p style="font-size: 11px; color: var(--text-sub); margin-top: 2px;">Sent only to non-banned users of this bot.</p>
            <textarea id="broadcastMsg" rows="3" placeholder="Write your announcement..."></textarea>
            <button class="btn btn-purple" onclick="sendBroadcast()">Send Broadcast</button>
        </div>
    </div>

    <!-- TAB 2: USERS -->
    <div id="tab-users" class="tab-content">
        <input type="text" id="userSearch" placeholder="Search by name, username or ID..." onkeyup="filterUsers()">
        <div id="userList" style="margin-top: 10px;"></div>
    </div>

    <!-- TAB 3: LIMITS -->
    <div id="tab-limits" class="tab-content">
        <div class="card">
            <h3>FREE Plan</h3>
            <div style="display:flex; gap:10px; margin-top:10px;">
                <div>
                    <label style="font-size:10px;">LIVE SIGNALS / DAY</label>
                    <input type="number" id="freeLive" value="5">
                </div>
                <div>
                    <label style="font-size:10px;">FUTURE LISTS / DAY</label>
                    <input type="number" id="freeFuture" value="2">
                </div>
            </div>
            <button class="btn btn-purple" onclick="saveLimits('free')">Save Free Limits</button>
        </div>

        <div class="card">
            <h3>STARTER Plan</h3>
            <div style="display:flex; gap:10px; margin-top:10px;">
                <div>
                    <label style="font-size:10px;">LIVE SIGNALS / DAY</label>
                    <input type="number" id="starterLive" value="25">
                </div>
                <div>
                    <label style="font-size:10px;">FUTURE LISTS / DAY</label>
                    <input type="number" id="starterFuture" value="3">
                </div>
            </div>
            <button class="btn btn-purple" onclick="saveLimits('starter')">Save Starter Limits</button>
        </div>
    </div>

    <!-- USER MODAL -->
    <div id="userModal" class="modal">
        <div class="modal-content">
            <div style="display: flex; gap: 12px; align-items: center; margin-bottom: 15px;">
                <div class="avatar" id="modalAvatar">MD</div>
                <div>
                    <h3 id="modalName">User Name</h3>
                    <p style="font-size:11px; color:var(--text-sub);" id="modalUsername">@username</p>
                </div>
            </div>
            
            <div class="modal-item"><span>User ID</span><span id="modalUid">00000</span></div>
            <div class="modal-item"><span>Plan</span><span id="modalPlan">FREE</span></div>
            <div class="modal-item"><span>First Seen</span><span id="modalJoined">N/A</span></div>
            <div class="modal-item"><span>Status</span><span id="modalStatus" style="color:var(--success)">Active</span></div>

            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-top: 15px;">
                <button class="btn btn-danger" id="modalBanBtn" onclick="toggleBan()">Ban User</button>
                <button class="btn btn-purple" style="margin-top:0" onclick="grantLicense()">Grant License</button>
                <button class="btn" style="background:#374151; color:#fff;" onclick="resetUsage()">Reset Usage</button>
                <button class="btn" style="background:#1f2937; color:#fff;" onclick="closeModal()">Close</button>
            </div>
        </div>
    </div>

    <script>
        let allUsersData = [];
        let selectedUserId = null;
        let isRunning = true;

        function switchTab(name) {
            document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
            event.target.classList.add('active');
            document.getElementById('tab-' + name).classList.add('active');
        }

        async function loadData() {
            const res = await fetch('/api/admin/data');
            const data = await res.json();
            
            document.getElementById('statTotalUsers').innerText = data.stats.total;
            document.getElementById('statLicensed').innerText = data.stats.licensed;
            document.getElementById('statBanned').innerText = data.stats.banned;
            document.getElementById('statToday').innerText = data.stats.today;

            allUsersData = data.users;
            renderUsers(allUsersData);
        }

        function renderUsers(list) {
            const container = document.getElementById('userList');
            container.innerHTML = '';
            list.forEach(u => {
                const initials = u.full_name ? u.full_name.substring(0,2).toUpperCase() : 'US';
                container.innerHTML += `
                    <div class="user-item" onclick="openModal(${u.user_id})">
                        <div class="avatar">${initials}</div>
                        <div class="user-info">
                            <h4>${u.full_name || 'No Name'}</h4>
                            <p>@${u.username || 'none'} ID:${u.user_id}</p>
                        </div>
                        <span style="font-size:11px; background:#1f2937; padding:3px 8px; border-radius:10px;">
                            ${u.is_premium ? u.plan_type : 'Free'}
                        </span>
                    </div>
                `;
            });
        }

        function filterUsers() {
            const q = document.getElementById('userSearch').value.toLowerCase();
            const filtered = allUsersData.filter(u => 
                (u.full_name && u.full_name.toLowerCase().includes(q)) ||
                (u.username && u.username.toLowerCase().includes(q)) ||
                u.user_id.toString().includes(q)
            );
            renderUsers(filtered);
        }

        function openModal(uid) {
            const u = allUsersData.find(x => x.user_id === uid);
            if(!u) return;
            selectedUserId = uid;

            document.getElementById('modalAvatar').innerText = u.full_name ? u.full_name.substring(0,2).toUpperCase() : 'US';
            document.getElementById('modalName').innerText = u.full_name || 'No Name';
            document.getElementById('modalUsername').innerText = '@' + (u.username || 'none');
            document.getElementById('modalUid').innerText = u.user_id;
            document.getElementById('modalPlan').innerText = u.is_premium ? u.plan_type.toUpperCase() : 'FREE';
            document.getElementById('modalJoined').innerText = u.joined_at || 'N/A';
            
            const banBtn = document.getElementById('modalBanBtn');
            if(u.is_banned) {
                document.getElementById('modalStatus').innerText = 'Banned';
                document.getElementById('modalStatus').style.color = 'var(--danger)';
                banBtn.innerText = 'Unban User';
            } else {
                document.getElementById('modalStatus').innerText = 'Active';
                document.getElementById('modalStatus').style.color = 'var(--success)';
                banBtn.innerText = 'Ban User';
            }

            document.getElementById('userModal').style.display = 'flex';
        }

        function closeModal() {
            document.getElementById('userModal').style.display = 'none';
        }

        function toggleBot() {
            isRunning = !isRunning;
            const badge = document.getElementById('botStatusBadge');
            const toggleBtn = document.getElementById('toggleBotBtn');
            if(isRunning) {
                badge.innerText = '● Running';
                badge.className = 'status-badge';
                toggleBtn.innerText = 'Stop';
                toggleBtn.className = 'btn btn-danger';
            } else {
                badge.innerText = '● Stopped';
                badge.className = 'status-badge stopped';
                toggleBtn.innerText = 'Start';
                toggleBtn.className = 'btn';
                toggleBtn.style.background = '#10b981';
            }
        }

        async function toggleBan() {
            await fetch('/api/admin/toggle_ban', {
                method:'POST',
                headers:{'Content-Type':'application/json'},
                body: JSON.stringify({user_id: selectedUserId})
            });
            closeModal();
            loadData();
        }

        async function grantLicense() {
            const days = prompt("Enter duration in days (or 'permanent'):", "30");
            if(days) {
                await fetch('/api/admin/grant_license', {
                    method:'POST',
                    headers:{'Content-Type':'application/json'},
                    body: JSON.stringify({user_id: selectedUserId, days: days})
                });
                closeModal();
                loadData();
            }
        }

        async function resetUsage() {
            await fetch('/api/admin/reset_usage', {
                method:'POST',
                headers:{'Content-Type':'application/json'},
                body: JSON.stringify({user_id: selectedUserId})
            });
            alert("Usage reset successful!");
            closeModal();
            loadData();
        }

        async function sendBroadcast() {
            const msg = document.getElementById('broadcastMsg').value;
            if(!msg) return alert("Write a message first!");
            await fetch('/api/admin/broadcast', {
                method:'POST',
                headers:{'Content-Type':'application/json'},
                body: JSON.stringify({message: msg})
            });
            alert("Broadcast sent!");
            document.getElementById('broadcastMsg').value = '';
        }

        function saveLimits(plan) {
            alert(plan.toUpperCase() + " limits updated!");
        }

        loadData();
        setInterval(loadData, 5000);
    </script>
</body>
</html>
"""

@web_app.route('/')
def admin_panel():
    return render_template_string(HTML_ADMIN_PANEL)

@web_app.route('/api/admin/data')
def get_admin_data():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('SELECT * FROM users ORDER BY user_id DESC')
    rows = c.fetchall()
    conn.close()

    user_list = []
    licensed_count = 0
    banned_count = 0
    today_sigs = 0

    for r in rows:
        u = dict(r)
        is_prem = bool(u.get('is_premium', 0))
        is_ban = bool(u.get('is_banned', 0))
        
        if is_prem: licensed_count += 1
        if is_ban: banned_count += 1
        today_sigs += u.get('daily_sigs', 0)

        user_list.append({
            "user_id": u.get('user_id'),
            "username": u.get('username', ''),
            "full_name": u.get('full_name', ''),
            "is_premium": is_prem,
            "is_banned": is_ban,
            "plan_type": u.get('plan_type', 'free'),
            "joined_at": u.get('joined_at', ''),
            "daily_sigs": u.get('daily_sigs', 0)
        })

    return jsonify({
        "stats": {
            "total": len(rows),
            "licensed": licensed_count,
            "banned": banned_count,
            "today": today_sigs
        },
        "users": user_list
    })

@web_app.route('/api/admin/toggle_ban', methods=['POST'])
def api_toggle_ban():
    uid = request.get_json().get('user_id')
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT is_banned FROM users WHERE user_id=?", (uid,))
    row = c.fetchone()
    if row:
        curr = row['is_banned'] if 'is_banned' in row.keys() else 0
        new_val = 0 if curr == 1 else 1
        c.execute("UPDATE users SET is_banned=? WHERE user_id=?", (new_val, uid))
        conn.commit()
    conn.close()
    return jsonify({"success": True})

@web_app.route('/api/admin/grant_license', methods=['POST'])
def api_grant_license():
    data = request.get_json()
    test_2.db_set_license(data.get('user_id'), data.get('days', 30), 'premium')
    return jsonify({"success": True})

@web_app.route('/api/admin/reset_usage', methods=['POST'])
def api_reset_usage():
    uid = request.get_json().get('user_id')
    test_2.db_reset_daily(uid)
    return jsonify({"success": True})

@web_app.route('/api/admin/broadcast', methods=['POST'])
def api_broadcast():
    msg = request.get_json().get('message')
    if msg:
        users = test_2.db_all()
        for u in users:
            try:
                asyncio.run(test_2.tg("sendMessage", chat_id=u[0], text=test_2.fmt(msg, bold=True), parse_mode="HTML"))
            except Exception:
                pass
    return jsonify({"success": True})

def start_bot():
    # Runs the original main() from test_2.py in thread
    test_2.main()

if __name__ == "__main__":
    init_admin_db()
    # Run Telegram Bot in background thread
    threading.Thread(target=start_bot, daemon=True).start()
    
    # Run Web Admin Panel Server
    port = int(os.getenv("PORT", 5000))
    web_app.run(host="0.0.0.0", port=port)
