import os
from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, DateTime, ForeignKey, Boolean, CheckConstraint
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")

if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

DB_PATH = os.path.join(DATA_DIR, "studio_marcia_nails.db")

engine = create_engine(f"sqlite:///{DB_PATH}", echo=False)
Base = declarative_base()

class Cliente(Base):
    __tablename__ = 'cliente'

    id = Column(Integer, primary_key=True, autoincrement=True)
    nome = Column(String, nullable=False)
    telefone = Column(String, nullable=False, unique=True)
    data_cadastro = Column(DateTime, default=datetime.utcnow, nullable=False)

    agendamentos = relationship("Agendamento", back_populates="cliente", cascade="all, delete-orphan")

class Agendamento(Base):
    __tablename__ = 'agendamento'

    id = Column(Integer, primary_key=True, autoincrement=True)
    cliente_id = Column(Integer, ForeignKey('cliente.id'), nullable=False)
    data_hora = Column(DateTime, nullable=False)
    servico = Column(String, nullable=False)
    status = Column(String, default='agendado', nullable=False)
    data_criacao = Column(DateTime, default=datetime.utcnow, nullable=False)

    cliente = relationship("Cliente", back_populates="agendamentos")


class UsuarioGestao(Base):
    __tablename__ = 'usuario_gestao'
    __table_args__ = (CheckConstraint("premium_concedidos BETWEEN 0 AND 3"),)
    id = Column(Integer, primary_key=True)
    email = Column(String(254), nullable=False, unique=True)
    papel = Column(String(20), nullable=False, default='gestor')
    nome = Column(String(100), nullable=False, default='')
    telefone = Column(String(20), nullable=False, default='')
    estabelecimento = Column(String(100), nullable=False, default='')
    slug = Column(String(80), nullable=False, unique=True)
    senha_hash = Column(String(100), nullable=True)
    redefinir = Column(Boolean, nullable=False, default=False)
    plano = Column(String(10), nullable=False, default='teste')
    ativado_em = Column(DateTime, nullable=True)
    vence_em = Column(DateTime, nullable=True)
    premium_concedidos = Column(Integer, nullable=False, default=0)


class SessaoGestao(Base):
    __tablename__ = 'sessao_gestao'
    token_hash = Column(String(64), primary_key=True)
    usuario_id = Column(Integer, ForeignKey('usuario_gestao.id'), nullable=False, index=True)
    csrf = Column(String(64), nullable=False)
    expira_em = Column(DateTime, nullable=False)


class FalhaAcesso(Base):
    __tablename__ = 'falha_acesso'
    chave = Column(String(64), primary_key=True)
    quantidade = Column(Integer, nullable=False, default=0)
    tentar_apos = Column(DateTime, nullable=False)
    ultima_falha = Column(DateTime, nullable=False)


class VinculoAgenda(Base):
    # As reservas antigas sem vínculo continuam pertencendo ao Studio Márcia Nails.
    __tablename__ = 'vinculo_agenda'
    agendamento_id = Column(Integer, ForeignKey('agendamento.id'), primary_key=True)
    usuario_id = Column(Integer, ForeignKey('usuario_gestao.id'), nullable=False, index=True)
    nome_cliente = Column(String(100), nullable=False)


Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)
session = Session()


# Cadastro inicial idempotente: nunca redefine senha ou plano de contas existentes.
from sqlalchemy.dialects.sqlite import insert as inserir_sqlite
with Session() as sessao_inicial:
    for conta in [
        {"email":os.environ.get("MARCIA_OWNER_EMAIL", "leocladison@gmail.com"), "papel":"proprietario", "nome":"Proprietário", "slug":"sistema", "plano":"pago"},
        {"email":"marcia@marcia.com", "papel":"gestor", "nome":"Márcia", "estabelecimento":"Studio Márcia Nails", "slug":"marcia-nails", "plano":"pago"},
    ]:
        sessao_inicial.execute(inserir_sqlite(UsuarioGestao).values(**conta).on_conflict_do_nothing(index_elements=['email']))
    sessao_inicial.commit()
