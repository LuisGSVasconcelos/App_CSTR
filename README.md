# ⚗️ Simulador de Reator CSTR Não Isotérmico

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![ttkbootstrap](https://img.shields.io/badge/ttkbootstrap-1.10.1-green)](https://ttkbootstrap.readthedocs.io/)

Um simulador educacional interativo de um **reator CSTR não isotérmico** com duas reações consecutivas e controle PID, desenvolvido para auxiliar no aprendizado de Engenharia Química.

![Interface do Simulador](cstr.jpg)  
*Exemplo da interface gráfica do simulador*

---

## 📚 Sobre o Projeto

Este aplicativo simula o comportamento dinâmico de um **Reator Contínuo de Tanque Agitado (CSTR)** onde ocorrem as reações:

- **A + B → C** (exotérmica)
- **A + C → D** (exotérmica)

O usuário pode interagir com o processo através de uma interface gráfica inspirada em salas de controle reais, ajustando vazões, concentrações de alimentação, temperatura e parâmetros dos controladores PID, observando em tempo real o efeito nos níveis, temperaturas e concentrações.

**Objetivo educacional:** Permitir que estudantes visualizem conceitos de cinética química, balanços de massa e energia, e sintonia de malhas de controle de forma lúdica e intuitiva, potencializando a aprendizagem através da experimentação virtual.

---

## ✨ Funcionalidades

- ✅ Modelagem dinâmica de CSTR com duas reações (cinética de Arrhenius).
- ✅ Controladores PID para **nível** (LIC-101) e **temperatura** (TIC-101).
- ✅ Interface gráfica moderna com abas de operação e configuração.
- ✅ Visualização em tempo real:
  - Nível, temperatura e concentrações de A e C no reator.
  - Abertura da válvula de saída e potência térmica aplicada.
- ✅ Ajuste contínuo de perturbações:
  - Vazão de alimentação.
  - Temperatura de entrada.
  - Concentrações de A e B na corrente de entrada.
- ✅ Sliders e faceplates para operação manual ou automática.
- ✅ Gráficos dinâmicos atualizados a cada passo.
- ✅ Salvamento do histórico de dados em CSV.
- ✅ Captura de tela da interface.
- ✅ Pausa e reset da simulação.

---

## 🛠️ Tecnologias Utilizadas

- **Python 3.8+**
- **Tkinter** + **ttkbootstrap** (para interface moderna)
- **Matplotlib** (gráficos dinâmicos)
- **NumPy** (cálculos numéricos)
- **Pandas** (manipulação de dados)
- **Pillow** (processamento de imagens)

---

## 📋 Pré-requisitos

- Python 3.8 ou superior instalado.
- Gerenciador de pacotes `pip`.

---

## 🚀 Instalação e Execução

1. **Clone o repositório:**
   ```bash
   git clone https://github.com/seu-usuario/App_CSTR.git
   cd App_CSTR
