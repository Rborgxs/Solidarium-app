from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey
from datetime import datetime
import json

Base = declarative_base()


class Client(Base):
    __tablename__ = 'clients'
    id = Column(Integer, primary_key=True)
    external_id = Column(String, unique=True, nullable=True)  # optional mapping to previous submission id
    nome = Column(String, nullable=True)
    cpf = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    answers = relationship('Answer', back_populates='client', cascade='all, delete-orphan')


class Question(Base):
    __tablename__ = 'questions'
    id = Column(Integer, primary_key=True)
    ord = Column(Integer, nullable=False, default=0)
    texto = Column(Text, nullable=False)
    tipo = Column(String, nullable=False)  # 'subjetiva' or 'objetiva'
    opcoes = Column(Text, nullable=True)   # JSON encoded list when applicable
    modo = Column(String, nullable=True)   # 'radio' or 'multiple' when objetiva
    obrigatoria = Column(Integer, default=0)
    answers = relationship('Answer', back_populates='question', cascade='all, delete-orphan')

    def get_opcoes(self):
        if not self.opcoes:
            return []
        try:
            return json.loads(self.opcoes)
        except Exception:
            return []


class Answer(Base):
    __tablename__ = 'answers'
    id = Column(Integer, primary_key=True)
    client_id = Column(Integer, ForeignKey('clients.id'), nullable=False)
    question_id = Column(Integer, ForeignKey('questions.id'), nullable=False)
    resposta = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

    client = relationship('Client', back_populates='answers')
    question = relationship('Question', back_populates='answers')
