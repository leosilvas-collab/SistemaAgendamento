"""Defina os acessos pelo console; senhas nunca são exibidas ou salvas em texto."""
import os
import re
from getpass import getpass
os.environ["MARCIA_OWNER_EMAIL"]="leocladison@leocladison.com"
import bcrypt
from models import Session, UsuarioGestao, SessaoGestao
from agenda import agora_sao_paulo, horario_local

def main():
    hashes={}
    for email in ("leocladison@leocladison.com","marcia@marcia.com"):
        while True:
            senha=getpass("Defina a senha de 6 números para "+email+": ")
            confirmar=getpass("Confirme a senha: ")
            if re.fullmatch(r"[0-9]{6}",senha) and senha==confirmar:
                hashes[email]=bcrypt.hashpw(senha.encode(),bcrypt.gensalt(12)).decode()
                del senha, confirmar
                break
            print("As senhas devem coincidir e conter exatamente seis números.")
    with Session() as s:
        for email,senha_hash in hashes.items():
            u=s.query(UsuarioGestao).filter_by(email=email).one()
            u.senha_hash=senha_hash
            u.redefinir=False
            u.ativado_em=u.ativado_em or horario_local(agora_sao_paulo())
            if email=="marcia@marcia.com":
                u.plano="pago"
            s.query(SessaoGestao).filter_by(usuario_id=u.id).delete()
        s.commit()
    print("Acessos configurados. Nenhuma senha foi exibida nem gravada em texto.")
if __name__=="__main__":
    main()
