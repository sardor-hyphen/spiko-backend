from flask import Blueprint, request, jsonify
import requests
import os
import ipaddress

geo_bp = Blueprint('geo', __name__)

def get_client_ip(req):
    """
    Extract the best-guess client IP.
    Trust the first IP in X-Forwarded-For if present.
    Fallback to remote_addr.
    """
    xff = req.headers.get('X-Forwarded-For', '')
    if xff:
        # Take the first non-empty trimmed item
        ip = xff.split(',')[0].strip()
    else:
        ip = req.remote_addr or ''

    # Basic validation
    try:
        ipaddress.ip_address(ip)
        return ip
    except ValueError:
        return ''

def get_country_code(req, ip):
    """
    Resolve ISO alpha-2 country code for the request.
    Priority:
    1) CDN headers (Cloudflare etc.)
    2) Fallback to ipapi.co lookup by IP
    Returns uppercase 2-letter code or '' if unknown.
    """
    # 1) CDN/Proxy headers
    # Cloudflare
    cf_cc = req.headers.get('CF-IPCountry')
    if cf_cc and len(cf_cc) == 2:
        return cf_cc.upper()

    # Common alt headers (if you add them at your edge)
    for hdr in ['X-Country-Code', 'X-Geo-Country', 'X-Appengine-Country']:
        v = req.headers.get(hdr)
        if v and len(v) == 2:
            return v.upper()

    # 2) Fallback to external API
    if not ip:
        return ''

    try:
        # ipapi returns keys: country, country_name, country_code
        r = requests.get(f'https://ipapi.co/{ip}/json/', timeout=5)
        r.raise_for_status()
        data = r.json()
        code = (data.get('country_code') or data.get('country') or '').upper().strip()
        if len(code) == 2:
            return code
        return ''
    except requests.RequestException:
        return ''

@geo_bp.route('/api/check_uzbek_user', methods=['GET'])
def check_uzbek_user():
    # Dev override
    dev_override = os.getenv('DEV_UZBEK_OVERRIDE', '').lower()
    if dev_override == 'true':
        return jsonify({"is_uzbek": True, "source": "dev_override"})

    # Get client IP
    ip = get_client_ip(request)

    # Local/dev handling: default to UZ-free if unknown or localhost/private
    is_private = False
    if ip:
        try:
            is_private = ipaddress.ip_address(ip).is_private
        except ValueError:
            is_private = True
    if not ip or is_private:
        # In dev or behind NAT without headers, default to free to avoid blocking UZ
        return jsonify({"is_uzbek": True, "source": "private_or_unknown_ip"})

    # Resolve country
    cc = get_country_code(request, ip)

    # If unknown country, choose safe default: free
    if not cc or cc in ('ZZ', '--'):
        return jsonify({"is_uzbek": True, "source": "unknown_country"})

    is_uzbek = (cc == 'UZ')
    return jsonify({
        "is_uzbek": is_uzbek,
        "country_code": cc,
        "ip": ip,
        "source": "header_or_lookup"
    })