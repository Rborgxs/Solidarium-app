from dataclasses import dataclass, field
from typing import List, Optional
from datetime import datetime
import json

@dataclass
class Client:
    id: Optional[int] = None
    external_id: Optional[str] = None
    nome: Optional[str] = None
    cpf: Optional[str] = None
    created_at: Optional[datetime] = None
    answers: List['AnswerV2'] = field(default_factory=list)


@dataclass
class QuestionV2:
    id: Optional[int] = None
    ord: int = 0
    texto: str = ""
    tipo: str = "subjetiva"
    opcoes: Optional[str] = None  # JSON encoded list when applicable
    modo: Optional[str] = None
    obrigatoria: int = 0
    answers: List['AnswerV2'] = field(default_factory=list)

    def get_opcoes(self):
        if not self.opcoes:
            return []
        try:
            return json.loads(self.opcoes)
        except Exception:
            return []


@dataclass
class AnswerV2:
    id: Optional[int] = None
    client_id: Optional[int] = None
    question_id: Optional[int] = None
    resposta: Optional[str] = None
    created_at: Optional[datetime] = None

