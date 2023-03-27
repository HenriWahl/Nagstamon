
$file = $args[0]
$cert_buffer = [System.Convert]::FromBase64String($env:WIN_SIGNING_CERT_BASE64)

$cert = [System.Security.Cryptography.X509Certificates.X509Certificate2]::New($cert_buffer, $env:WIN_SIGNING_PASSWORD)
Set-AuthenticodeSignature -HashAlgorithm SHA256 -Certificate $cert -TimestampServer http://timestamp.digicert.com -FilePath $file