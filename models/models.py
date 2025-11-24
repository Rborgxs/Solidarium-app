from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Text
from datetime import datetime

Base = declarative_base()


class Form(Base):
    __tablename__ = 'forms'
    id = Column(Integer, primary_key=True)
    titulo = Column(String, nullable=False)
    perguntas = relationship('Question', back_populates='form', cascade='all, delete-orphan', order_by='Question.ord')


class Question(Base):
    __tablename__ = 'questions'
    id = Column(Integer, primary_key=True)
    form_id = Column(Integer, ForeignKey('forms.id'), nullable=False)
    ord = Column(Integer, nullable=False)
    texto = Column(Text, nullable=False)
    tipo = Column(String, nullable=False)  # 'subjetiva' or 'objetiva'
    opcoes = relationship('Option', back_populates='question', cascade='all, delete-orphan', order_by='Option.id')
    form = relationship('Form', back_populates='perguntas')


class Option(Base):
    __tablename__ = 'options'
    id = Column(Integer, primary_key=True)
    question_id = Column(Integer, ForeignKey('questions.id'), nullable=False)
    texto = Column(String, nullable=False)
    question = relationship('Question', back_populates='opcoes')


class Submission(Base):
    __tablename__ = 'submissions'
    id = Column(String, primary_key=True)  # uuid hex
    form_id = Column(Integer, ForeignKey('forms.id'), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    answers = relationship('Answer', back_populates='submission', cascade='all, delete-orphan')


class Answer(Base):
    __tablename__ = 'answers'
    id = Column(Integer, primary_key=True)
    submission_id = Column(String, ForeignKey('submissions.id'), nullable=False)
    question_id = Column(Integer, ForeignKey('questions.id'), nullable=False)
    resposta = Column(Text)
    submission = relationship('Submission', back_populates='answers')
