#!/bin/sh
# Points nginx at the Let's Encrypt certificate once certbot has one. Until
# then a short-lived self-signed one lets nginx start (and answer the ACME
# challenge on port 80). Runs before nginx starts, then keeps watching so
# a first issue or a renewal is picked up without a restart.
set -eu

LIVE="/etc/letsencrypt/live/${DOMAIN}"
CERTS=/etc/nginx/certs

link_certs() {
    mkdir -p "$CERTS"
    if [ -f "$LIVE/fullchain.pem" ]; then
        ln -sf "$LIVE/fullchain.pem" "$CERTS/fullchain.pem"
        ln -sf "$LIVE/privkey.pem" "$CERTS/privkey.pem"
    elif [ ! -e "$CERTS/privkey.pem" ]; then
        echo "certs: no Let's Encrypt certificate for ${DOMAIN} yet, using a self-signed one"
        openssl req -x509 -nodes -newkey rsa:2048 -days 7 -subj "/CN=${DOMAIN}" \
            -keyout "$CERTS/privkey.pem" -out "$CERTS/fullchain.pem" 2>/dev/null
    fi
}

link_certs

(
    last=$(cksum < "$CERTS/fullchain.pem")
    while sleep 300; do
        link_certs
        now=$(cksum < "$CERTS/fullchain.pem")
        if [ "$now" != "$last" ]; then
            echo "certs: certificate changed, reloading nginx"
            nginx -s reload
            last=$now
        fi
    done
) &
