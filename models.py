import os
from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, DateTime, ForeignKey
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

Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)
session = Session()
