# Simulador de Reator CSTR Nao-Isotérmico para Etoxilacao

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/)
[![tkinter](https://img.shields.io/badge/UI-tkinter-ff69b4)](https://docs.python.org/3/library/tkinter.html)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**Simulador educacional interativo** de um reator CSTR (*Continuous Stirred Tank Reactor*) não-isotérmico com cinética de etoxilação e controle PID. Desenvolvido para apoiar disciplinas de Graduação e Pos-Graduação em Engenharia Química, permitindo que estudantes experimentem conceitos de cinética, balanços de massa/energia e controle de processos em tempo real.

![Interface do Simulador](cstr.jpg)

---

## Sumario

- [Fundamentação Teórica](#fundamentacao-teorica)
  - [Esquema Reacional](#esquema-reacional)
  - [Cinética Química](#cinetica-quimica)
  - [Balanço de Massa](#balanco-de-massa)
  - [Balanco de Energia](#balanco-de-energia)
  - [Balanco de Volume](#balanco-de-volume)
  - [Controle PID](#controle-pid)
- [Estrutura do Projeto](#estrutura-do-projeto)
- [Pre-requisitos](#pre-requisitos)
- [Instalação e Execução](#instalacao-e-execução)
- [Funcionalidades](#funcionalidades)
- [Guia de Uso](#guia-de-uso)
  - [Painel de Operação](#painel-de-operacao)
  - [Parâmetros e Sintonia](#parametros-e-sintonia)
  - [Controles Gerais](#controles-gerais)
- [Interpretação de Resultados](#interpretacao-de-resultados)
- [Extensoes Possíveis](#extensoes-possiveis)
- [Referências](#referencias)
- [Autor](#autor)

---

## Fundamentação Teórica

### Esquema Reacional

O reator modela duas reações exotérmicas consecutivas:

```
(1)  A + B  -->  C        (reação principal - formacao de surfactante)
(2)  A + C  -->  D        (reação secundária - subproduto indesejado)
```

Onde:

| Símbolo | Componente      | Função                         |
|---------|-----------------|----------------------------------|
| A       | Alcool graxo    | Reagente                         |
| B       | Oxido de Etileno| Reagente gasoso                  |
| C       | Surfactante     | **Produto desejado**             |
| D       | Subproduto      | Produto da reacao consecutiva    |

### Cinetica Quimica

Ambas as reacoes seguem cinetica elementar de 2a ordem. A constante de velocidade e dada pela **Lei de Arrhenius**:


$$ k_i(T) = A_i * exp(-E_i / (R * T)) $$

$$ r_1 = k_1 * C_A * C_B $$
$$ r_2 = k_2 * C_C * C_A $$



Onde:

-  $ A_i $: fator pre-exponencial ($ m^3/mol.s $)
- $ E_i $: energia de ativacao ($J/mol$)
- $ R = 8.314 J/mol.K $: constante universal dos gases
- $ T $: temperatura absoluta (K)

### Balanco de Massa

Para um CSTR com volume variavel, o balanco molar para cada especie i partindo de  

$$ d(N_i)/dt = F_{in}.C_i^{in} - F_{out}.C_i + V * \sum {(nu_{ij} *)} $$

 resulta em:


$$ dC_A/dt = (F_{in} / V) * (C_A^{in} - C_A) - r_1 - r_2 $$

$$ dC_B/dt = (F_{in} / V) * (C_B^{in} - C_B) - 2*r_1 $$

$$ dC_C/dt = (F_{in} / V) * (0 - C_C) + r_1 - r_2 $$

$$ dC_D/dt = (F_{in} / V) * (0 - C_D) + r_2 $$

### Balanco de Energia

Para um CSTR nao-isotermico com camisa de aquecimento/resfriamento:

$$
dT/dt = \frac {[Q_{sensivel} + Q_{reacao} + Q_{jack}]} {(rho * Cp * V)} $$

Onde:

- $Q_{sensivel} = F_{in} * rho * Cp * (T_{in} - T) $: calor sensivel da alimentação
- $Q_{reacao} = -\Delta{H_1} * r_1 * V - \Delta{H_2} * r_2 * V $: calor liberado pelas reações
- $Q_{jack}$: calor trocado com a camisa (split-range, veja abaixo)
- $rho$: densidade da mistura $(kg/m^3)$
- $Cp$: capacidade calorifica ($J/kg.K$)

### Balanco de Volume (Nivel)

O nivel no tanque e governado pela diferenca entre vazao de entrada e saida:

$$
dV/dt = F_{in} - F_{out}
$$
Onde:

$
F_{out} = Cv * f * \sqrt{h}
$

$ h = \frac{V }{Area}  $      (nivel)

$f = \frac{OP}{100} $       (fratura de abertura da valvula)


## Controle Termico Split-Range

O sistema utiliza uma estrategia de faixa dividida (*split-range*) para acionar mutuamente exclusivos:

| Sinal (%)      | Ação          | Atuador               |
|----------------|---------------|-----------------------|
| 0 - 49         | Resfriamento  | Valvula de agua fria  |
| 50             | Neutro        | Nenhum                |
| 51 - 100       | Aquecimento   | Valvula de vapor      |

### Controle PID

Dois controladores PID operam em cascata:

- **LIC-101 (Nivel)**: Kp = -60 (acao reversa: nivel alto -> saida diminui -> valvula fecha)
- **TIC-101 (Temperatura)**: Kp = +8 (acao direta: temperatura alta -> saida aumenta -> resfria)

A equacao implementada:

$$
u(t) = Kp * e(t) + Ki * \int{e dt} + Kd * \frac{de}{dt}
$$
$$
e = SP - PV
$$

---

## Estrutura do Projeto

```text
App_CSTR/
├── main.py                # Interface gráfica (sala de controle)
├── model.py               # Modelo matemático do CSTR (EDOs)
├── pid.py                 # Controlador PID digital com anti-windup
├── components/
│   ├── tank_widget.py     # Visualização animada do tanque (Canvas)
│   └── faceplate.py       # Painel do controlador (DCS-style)
├── cstr.jpg               # Screenshot da interface
└── UFCG_logo_png.png      # Logotipo da universidade
```

Cada modulo contem docstrings com as equacoes e a logica de modelagem, servindo tambem como material de consulta.

---

## Pre-requisitos

- **Python 3.8 ou superior**
- Gerenciador de pacotes `pip`
- Sistema operacional: Windows, Linux ou macOS

---

## Instalacao e Execucao

1. Clone o repositorio:

```bash
git clone https://github.com/LVasconcelos96/App_CSTR.git
cd App_CSTR
```

2. Instale as dependencias:

```bash
pip install -r requirements.txt
```

Caso nao exista `requirements.txt`, instale manualmente:

```bash
pip install numpy pandas matplotlib pillow ttkbootstrap
```

3. Execute o simulador:

```bash
python main.py
```

---

## Funcionalidades

- **Modelagem fenomenologica** de CSTR com 2 reacoes exotermicas (cinetica de Arrhenius)
- **Controladores PID** para nivel (LIC-101) e temperatura (TIC-101)
- **Modo de operacao** AUTO (PID calcula) e MANUAL (operador define)
- **Graficos dinamicos** em tempo real: nivel, temperatura, concentracoes, saidas dos controladores
- **Slider de vazao** para aplicar perturbacoes na alimentacao
- **Janela de historico** ajustavel (50 a 5000 s)
- **Exportacao CSV** dos dados simulados
- **Captura de tela** da interface
- **Placar de gamificacao** com razao produto/subproduto como metrica de desempenho
- **Reset completo** da simulacao (modelo + PIDs + historico)
- **Parametros editaveis**: ganhos PID, area do tanque, Cv da valvula, constantes cineticas

---

## Guia de Uso

### Painel de Operacao

A aba principal apresenta uma divisao em dois paineis:

**Painel Esquerdo (Processo)**

- **Tanque animado**: o nivel do liquido e a cor (azul = frio, vermelho = quente) refletem o estado do reator
- **Slider de Vazao**: ajusta a perturbacao na alimentacao (F_in) em tempo real
- **Janela do Grafico**: controla quantos segundos de historico sao exibidos nos graficos
- **Concentracoes**: leitura numerica de CA, CB, CC, CD no reator
- **Placar**: mostra tempo de simulacao, mols acumulados de produto (C) e subproduto (D), e a razao C/D como indicador de desempenho

**Painel Direito (Controle e Graficos)**

- **Faceplates**: LIC-101 (nivel) e TIC-101 (temperatura). Cada faceplate exibe:
  - PV (Process Variable): valor medido em tempo real
  - SP (Setpoint): valor desejado, editavel via campo ou slider
  - OP (Output): sinal de saida (0-100%)
  - Botoes AUTO/MAN para alternar o modo de operacao
- **Graficos**: seis graficos atualizados a cada 0.5 s:
  1. Nivel (m) — PV e SP
  2. Temperatura (C) — PV e SP
  3. Concentracao de Alcool (mol/m^3)
  4. Abertura da valvula de saida (%)
  5. Sinal termico split-range (0 = frio, 100 = vapor)
  6. Concentracao de Surfactante (mol/m^3)

### Parametros e Sintonia

Na segunda aba, e possivel modificar:

**Controladores PID:**
- Kp (ganho proporcional)
- Ki (ganho integral)
- Kd (ganho derivativo)

Dica de sintonia: comecce ajustando Kp para a resposta desejada, depois Ki para eliminar offset e, por fim, Kd para amortecer oscilacoes.

**Constantes do Sistema:**
- Area da secao transversal (m^2)
- Coeficiente de valvula Cv
- Fatores pre-exponenciais (A1, A2) e energias de ativacao (E1, E2)

Apos alterar os valores, clique em **SALVAR ALTERACOES**.

### Controles Gerais

| Botao         | Funcao                                       |
|---------------|----------------------------------------------|
| PAUSAR/RESUMIR| Interrompe ou retoma a simulacao             |
| RESETAR       | Reinicia reator, PIDs, historico e placar    |
| SALVAR DADOS  | Exporta o historico para CSV                 |
| CAPTURA       | Salva screenshot da janela                   |

---

## Interpretacao de Resultados

- **Razao C/D > 10**: operacao excelente (alta seletividade ao produto desejado)
- **Razao C/D entre 5 e 10**: atencao (formacao significativa de subproduto)
- **Razao C/D < 5**: operacao ineficiente (reacao consecutiva predominante)

A razao C/D e influenciada principalmente por:
- Temperatura do reator (T alta favorece D, pois E2 > E1)
- Tempo de residencia (vazao de alimentacao x nivel)
- Concentracao de alimentacao de B

---

## Extensoes Possiveis

Este simulador pode ser estendido academicamente para explorar:

- **Controle em cascata** entre malhas de temperatura e vazao de refrigerante
- **Controle feedforward** para rejeicao de perturbacoes na vazao de alimentacao
- **Otimizacao em tempo real (RTO)** com funcao objetivo de maximizar razao C/D
- **Estimacao de estados** (filtro de Kalman) para concentracoes nao medidas
- **Controle preditivo (MPC)** substituindo os PIDs
- **Trocador de calor** explicito com balanco do lado da camisa
- **Modelagem da cinetica** com ordens de reacao nao elementares

---

## Referencias

1. Fogler, H. S. (2016). *Elements of Chemical Reaction Engineering* (5th ed.). Prentice Hall.
2. Seborg, D. E., Edgar, T. F., Mellichamp, D. A., & Doyle, F. J. (2016). *Process Dynamics and Control* (4th ed.). Wiley.
3. Smith, J. M., Van Ness, H. C., & Abbott, M. M. (2005). *Introduction to Chemical Engineering Thermodynamics* (7th ed.). McGraw-Hill.
4. Marlin, T. E. (2000). *Process Control: Designing Processes and Control Systems for Dynamic Performance* (2nd ed.). McGraw-Hill.

---

## Autor

**Luis Vasconcelos** - Laboratorio LARCA | Universidade Federal de Campina Grande (UFCG)

*Disciplina: Controle de Processos - Graduação e Pos-Graduação em Engenharia Quimica*
