# Imagen unica para spines, leafs y hosts (FRR + sshd + herramientas de red)
FROM frrouting/frr:latest
RUN apk add --no-cache openssh-server bash iproute2 iputils bridge-utils tcpdump iperf3 python3 curl \
 && sed -i 's/^ospfd=no/ospfd=yes/; s/^bgpd=no/bgpd=yes/; s/^bfdd=no/bfdd=yes/' /etc/frr/daemons \
 && echo 'root:gsm12345' | chpasswd \
 && sed -i 's#^root:\(.*\):/bin/ash#root:\1:/bin/bash#' /etc/passwd \
 && printf 'PermitRootLogin yes\nPasswordAuthentication yes\nUsePAM no\n' > /etc/ssh/sshd_config \
 && printf "export PS1='\\\\h:\\\\w# '\n" > /root/.bash_profile \
 && cp /root/.bash_profile /root/.bashrc
COPY start.sh /start.sh
RUN chmod +x /start.sh
CMD ["/start.sh"]
