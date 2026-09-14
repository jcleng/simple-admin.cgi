#!/bin/sh

# ========== 基础配置 ==========
USER="${DOCKERADMIN_USER:-admin}"
PASS="${DOCKERADMIN_PASS:-admin}"
COOKIE_NAME="dockerauth"

# ========== HTTP 工具函数 ==========
header() {
    printf "Content-Type: text/html; charset=utf-8\r\n\r\n"
}

redirect() {
    printf "Status: 302 Found\r\n"
    printf "Location: %s\r\n\r\n" "$1"
    exit 0
}

html_escape() {
    sed 's/&/\&amp;/g; s/</\&lt;/g; s/>/\&gt;/g; s/"/\&quot;/g'
}

# ========== Cookie / Auth ==========
COOKIE=$(echo "$HTTP_COOKIE" | tr ';' '\n' | grep "${COOKIE_NAME}=" | cut -d= -f2-)
AUTH_OK=0

if [ "$COOKIE" = "$(echo -n "$USER$PASS" | md5sum | cut -c1-32)" ]; then
    AUTH_OK=1
fi

# ========== 登录处理 ==========
if [ "$AUTH_OK" -eq 0 ]; then
    if [ "$REQUEST_METHOD" = "POST" ]; then
        read -r -n "$CONTENT_LENGTH" POST_DATA
        U=$(echo "$POST_DATA" | sed 's/.*u=\([^&]*\).*/\1/')
        P=$(echo "$POST_DATA" | sed 's/.*p=\([^&]*\).*/\1/')

        if [ "$U" = "$USER" ] && [ "$P" = "$PASS" ]; then
            HASH=$(echo -n "$USER$PASS" | md5sum | cut -c1-32)
            printf "Status: 302 Found\r\n"
            printf "Set-Cookie: %s=%s; Path=/\r\n" "$COOKIE_NAME" "$HASH"
            printf "Location: /cgi-bin/dockeradmin.cgi\r\n\r\n"
            exit 0
        fi
        ERR="Invalid credentials"
    fi

    header
    cat <<EOF
<!doctype html>
<html><head><title>Docker Login</title></head>
<body style="font-family:system-ui;display:flex;justify-content:center;align-items:center;height:100vh;background:#f5f5f5">
<form method="post" style="background:#fff;padding:20px;border-radius:8px;width:280px;box-shadow:0 2px 8px rgba(0,0,0,.1)">
<h3>Docker Admin Login</h3>
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
    printf "Set-Cookie: %s=; Path=/; Max-Age=0\r\n" "$COOKIE_NAME"
    printf "Location: /cgi-bin/dockeradmin.cgi\r\n\r\n"
    exit 0
fi

# ========== 动作处理 ==========
CONTAINER=$(echo "$QUERY_STRING" | sed 's/.*c=\([^&]*\).*/\1/; s/%2F/\//g')
ACT=$(echo "$QUERY_STRING" | sed 's/.*act=\([^&]*\).*/\1/')

if [ -n "$CONTAINER" ]; then
    case "$ACT" in
        start)
            docker start "$CONTAINER" >/dev/null 2>&1
            ;;
        stop)
            docker stop "$CONTAINER" >/dev/null 2>&1
            ;;
        restart)
            docker restart "$CONTAINER" >/dev/null 2>&1
            ;;
        remove)
            STATUS=$(docker inspect -f '{{.State.Status}}' "$CONTAINER" 2>/dev/null)
            if [ "$STATUS" = "exited" ] || [ "$STATUS" = "created" ]; then
                docker rm "$CONTAINER" >/dev/null 2>&1
            fi
            ;;
        log)
            header
            echo "<pre>"
            docker logs --tail 200 "$CONTAINER" 2>&1 | html_escape
            echo "</pre>"
            exit 0
            ;;
    esac
    redirect "/cgi-bin/dockeradmin.cgi"
fi

# ========== 主页面 ==========
header
cat <<EOF
<!doctype html>
<html><head><title>Docker Container Manager</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
body{font-family:system-ui;padding:20px;background:#f7f7f7}
.topbar{display:flex;justify-content:space-between;align-items:center;margin-bottom:15px}
table{width:100%;border-collapse:collapse;background:#fff}
th,td{padding:8px 10px;border-bottom:1px solid #eee;text-align:left}
a{text-decoration:none;padding:4px 8px;border-radius:4px;font-size:12px;margin-right:4px;color:#fff}
.start{background:#28a745}.stop{background:#dc3545}.restart{background:#ffc107;color:#000}
.remove{background:#343a40}.log{background:#6c757d}.logout{background:#dc3545;padding:6px 12px;border-radius:4px}
.running{background:#d4edda;color:#155724}.stopped{background:#f8d7da;color:#721c24}
pre{margin:0;font-size:12px;padding:4px 6px;border-radius:4px;display:inline-block;min-width:180px}
</style>
</head>
<body>
<div class="topbar">
<h2>Docker Container Manager</h2>
<a class="logout" href="/cgi-bin/dockeradmin.cgi?logout">Logout</a>
</div>
<table>
<tr><th>Container</th><th>Status</th><th>Actions</th></tr>
EOF

for CID in $(docker ps -a --format '{{.Names}}'); do
    STATUS=$(docker inspect -f '{{.State.Status}}' "$CID")
    [ "$STATUS" = "running" ] && CLS="running" || CLS="stopped"

    ESC_CID=$(echo "$CID" | html_escape)

    cat <<EOF
<tr>
<td>$ESC_CID</td>
<td><pre class="$CLS">$(echo "$STATUS" | html_escape)</pre></td>
<td>
<a class="start" href="/cgi-bin/dockeradmin.cgi?act=start&c=$ESC_CID">Start</a>
<a class="stop" href="/cgi-bin/dockeradmin.cgi?act=stop&c=$ESC_CID">Stop</a>
<a class="restart" href="/cgi-bin/dockeradmin.cgi?act=restart&c=$ESC_CID">Restart</a>
<a class="remove" href="/cgi-bin/dockeradmin.cgi?act=remove&c=$ESC_CID"
   onclick="return confirm('Remove container $ESC_CID?')">Remove</a>
<a class="log" href="/cgi-bin/dockeradmin.cgi?act=log&c=$ESC_CID" target="_blank">Log</a>
</td>
</tr>
EOF
done

echo "</table></body></html>"
