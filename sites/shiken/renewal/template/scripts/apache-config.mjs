import {redirects} from './legacy-pages.mjs';
// .htaccess of the release (Xserver, Apache).  The first lines are the ones every site of this repository has (the server's page cache, calendar files).
export function apacheConfig(){return `SetEnvIf Request_URI ".*" Ngx_Cache_NoCacheMode=off
SetEnvIf Request_URI ".*" Ngx_Cache_AllCacheMode
SetEnvIf Request_URI "^/m/" Ngx_Cache_NoCacheMode=on
ErrorDocument 404 /404.html
AddDefaultCharset UTF-8
AddType image/webp .webp
AddType text/calendar .ics
RewriteEngine On
# Old pages that are the same exam as a detail page go there with one redirect (301).
${Object.entries(redirects).map(([from,to])=>`RewriteRule ^${from.slice(1,-1)}/?$ https://shiken-nittei.com${to} [R=301,L,NE]`).join('\n')}
RewriteCond %{HTTPS} !=on [OR]
RewriteCond %{HTTP_HOST} !^shiken-nittei\\.com$ [NC]
RewriteRule ^ https://shiken-nittei.com%{REQUEST_URI} [R=301,L,NE]
RewriteCond %{THE_REQUEST} \\s/+(.*/)?index\\.html[?\\s] [NC]
RewriteRule ^(.*)index\\.html$ https://shiken-nittei.com/$1 [R=301,L,NE]
<IfModule mod_headers.c>
 Header set X-Content-Type-Options "nosniff"
 Header set Referrer-Policy "strict-origin-when-cross-origin"
 Header set Cache-Control "no-cache"
 SetEnvIf Request_URI "^/_versions/" immutable_asset
 Header set Cache-Control "public, max-age=31536000, immutable" env=immutable_asset
</IfModule>
`}
