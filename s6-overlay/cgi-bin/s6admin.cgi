#!/bin/sh

# ========== 基础配置 ==========
SVC_DIR="/run/service"
LOG_DIR="/var/log"
USER="${S6ADMIN_USER:-admin}"
PASS="${S6ADMIN_PASS:-admin}"

# ========== HTTP 工具函数 ==========
header() {
    printf "Content-Type: text/html; charset=utf-8\r\n"
    printf "\r\n"
}

redirect() {
    printf "Status: 302 Found\r\n"
    printf "Location: %s\r\n\r\n" "$1"
    exit 0
}

html_escape() {
    sed 's/&/\&amp;/g; s/</\&lt;/g; s/>/\&gt;/g; s/"/\&quot;/g'
}

# ========== Session（简化版 cookie） ==========
COOKIE=$(echo "$HTTP_COOKIE" | tr ';' '\n' | grep 's6auth=' | cut -d= -f2-)
AUTH_OK=0

if [ "$COOKIE" = "$(echo -n "$USER$PASS" | md5sum | cut -c1-32)" ]; then
    AUTH_OK=1
fi

# ========== 登录处理 ==========
if [ "$AUTH_OK" -eq 0 ]; then
    if [ "$REQUEST_METHOD" = "POST" ]; then
        read -n "$CONTENT_LENGTH" POST_DATA
        U=$(echo "$POST_DATA" | sed 's/.*u=\([^&]*\).*/\1/; s/%40/@/g; s/%20/ /g')
        P=$(echo "$POST_DATA" | sed 's/.*p=\([^&]*\).*/\1/')

        if [ "$U" = "$USER" ] && [ "$P" = "$PASS" ]; then
            HASH=$(echo -n "$USER$PASS" | md5sum | cut -c1-32)
            printf "Status: 302 Found\r\n"
            printf "Set-Cookie: s6auth=%s; Path=/\r\n" "$HASH"
            printf "Location: /cgi-bin/s6admin.cgi\r\n\r\n"
            exit 0
        fi

        ERR="Invalid credentials"
    fi

    header
    cat <<EOF
<!doctype html>
<html><head><title>s6 Login</title></head>
<body style="font-family:system-ui;display:flex;justify-content:center;align-items:center;height:100vh;background:#f5f5f5">
<form method="post" style="background:#fff;padding:20px;border-radius:8px;width:280px;box-shadow:0 2px 8px rgba(0,0,0,.1)">
<h3>s6 Admin Login</h3>
$([ -n "$ERR" ] && echo "<p style='color:red'>$ERR</p>")
<input name="u" placeholder="Username" required style="width:100%;margin-bottom:10px;padding:8px">
<input name="p" type="password" placeholder="Password" required style="width:100%;margin-bottom:10px;padding:8px">
<button style="width:100%;padding:8px;background:#007bff;color:#fff;border:none;cursor:pointer">Login</button>
</form>
</body></html>
EOF
    exit 0
fi

# ========== 退出 ==========
if echo "$QUERY_STRING" | grep -q "logout"; then
    printf "Status: 302 Found\r\n"
    printf "Set-Cookie: s6auth=; Path=/; Max-Age=0\r\n"
    printf "Location: /cgi-bin/s6admin.cgi\r\n\r\n"
    exit 0
fi

# ========== 动作处理 ==========
SVC=$(echo "$QUERY_STRING" | sed 's/.*s=\([^&]*\).*/\1/; s/%2F/\//g')
ACT=$(echo "$QUERY_STRING" | sed 's/.*act=\([^&]*\).*/\1/')

if [ -n "$SVC" ] && [ -d "$SVC_DIR/$SVC" ]; then
    case "$ACT" in
        start)   s6-svc -u "$SVC_DIR/$SVC" ;;
        stop)    s6-svc -d "$SVC_DIR/$SVC" ;;
        restart) s6-svc -r "$SVC_DIR/$SVC" ;;
        reload)  s6-svc -h "$SVC_DIR/$SVC" ;;
        log)
            LOG="$LOG_DIR/$SVC/current"
            header
            echo "<pre>"
            if [ -f "$LOG" ]; then
                tail -n 200 "$LOG" | html_escape
            else
                echo "No log found: $LOG"
            fi
            echo "</pre>"
            exit 0
            ;;
    esac
    redirect "/cgi-bin/s6admin.cgi"
fi

# ========== 主页面 ==========
header
cat <<EOF
<!doctype html>
<html><head><title>s6 Service Manager</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
body{font-family:system-ui;padding:20px;background:#f7f7f7}
.topbar{display:flex;justify-content:space-between;align-items:center;margin-bottom:15px}
table{width:100%;border-collapse:collapse;background:#fff}
th,td{padding:8px 10px;border-bottom:1px solid #eee;text-align:left}
a{text-decoration:none;padding:4px 8px;border-radius:4px;font-size:12px;margin-right:4px;color:#fff}
.start{background:#28a745}.stop{background:#dc3545}.restart{background:#ffc107;color:#000}
.reload{background:#17a2b8}.log{background:#6c757d}.logout{background:#dc3545;padding:6px 12px;border-radius:4px}
.up{background:#d4edda;color:#155724}.down{background:#f8d7da;color:#721c24}
pre{margin:0;font-size:12px;padding:4px 6px;border-radius:4px;display:inline-block;min-width:180px}
</style>
</head>
<body>
<div class="topbar">
<h2>s6-overlay Service Manager</h2>
<a class="logout" href="/cgi-bin/s6admin.cgi?logout">Logout</a>
</div>
<table>
<tr><th>Service</th><th>Status</th><th>Actions</th></tr>
EOF

for SVC in $(ls "$SVC_DIR"); do
    [ "$SVC" = "." ] && continue
    [ "$SVC" = ".." ] && continue
    [ -d "$SVC_DIR/$SVC" ] || continue
    [ "${SVC#.}" != "$SVC" ] && continue

    STATUS=$(s6-svstat "$SVC_DIR/$SVC")
    if echo "$STATUS" | grep -q "up"; then
        CLS="up"
    elif echo "$STATUS" | grep -q "down"; then
        CLS="down"
    else
        CLS="unknown"
    fi

    ESC_SVC=$(echo "$SVC" | html_escape)

    cat <<EOF
<tr>
<td>$ESC_SVC</td>
<td><pre class="$CLS">$(echo "$STATUS" | html_escape)</pre></td>
<td>
<a class="start" href="/cgi-bin/s6admin.cgi?act=start&s=$ESC_SVC">Start</a>
<a class="stop" href="/cgi-bin/s6admin.cgi?act=stop&s=$ESC_SVC">Stop</a>
<a class="restart" href="/cgi-bin/s6admin.cgi?act=restart&s=$ESC_SVC">Restart</a>
<a class="reload" href="/cgi-bin/s6admin.cgi?act=reload&s=$ESC_SVC">Reload</a>
<a class="log" href="/cgi-bin/s6admin.cgi?act=log&s=$ESC_SVC" target="_blank">Log</a>
</td>
</tr>
EOF
done

echo "</table></body></html>"
