# waylo_music_flask

## to resintall SSL sert !! 
## get new keys and pems from namecheap then edit this conf 
```
  366  sudo vim /etc/apache2/sites-enabled/000-default.conf
  367  history
  368  sudo service apache2 restart
  369  history



- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
Congratulations! You have successfully enabled https://waylomusic.com

You should test your configuration at:
https://www.ssllabs.com/ssltest/analyze.html?d=waylomusic.com
- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -

IMPORTANT NOTES:
 - Congratulations! Your certificate and chain have been saved at:
   /etc/letsencrypt/live/waylomusic.com/fullchain.pem
   Your key file has been saved at:
   /etc/letsencrypt/live/waylomusic.com/privkey.pem
   Your cert will expire on 2026-02-20. To obtain a new or tweaked
   version of this certificate in the future, simply run certbot again
   with the "certonly" option. To non-interactively renew *all* of
   your certificates, run "certbot renew"
 - Your account credentials have been saved in your Certbot
   configuration directory at /etc/letsencrypt. You should make a
   secure backup of this folder now. This configuration directory will
   also contain certificates and private keys obtained by Certbot so
   making regular backups of this folder is ideal.
 - If you like Certbot, please consider supporting our work by:

   Donating to ISRG / Let's Encrypt:   https://letsencrypt.org/donate
   Donating to EFF:                    https://eff.org/donate-le
```
