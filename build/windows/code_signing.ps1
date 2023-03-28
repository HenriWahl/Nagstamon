# get file to be signed from first argument
$file = $args[0]

# decode base64 PFX from environment variable
$cert_buffer = [System.Convert]::FromBase64String($env:WIN_SIGNING_CERT_BASE64)

# open cert from PFX with password
$cert = [System.Security.Cryptography.X509Certificates.X509Certificate2]::New($cert_buffer, $env:WIN_SIGNING_PASSWORD)

# finally sign the given file
Set-AuthenticodeSignature -HashAlgorithm SHA256 -Certificate $cert -TimestampServer http://timestamp.sectigo.com -FilePath $file