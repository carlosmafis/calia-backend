# services/ocr_service.py

import cv2
import numpy as np
from PIL import Image, ImageOps


# ==========================
# FUNÇÃO PARA ORDENAR PONTOS (PERSPECTIVA)
# ==========================

def order_points(pts):

    rect = np.zeros((4,2), dtype="float32")

    s = pts.sum(axis=1)
    rect[0] = pts[np.argmin(s)]
    rect[2] = pts[np.argmax(s)]

    diff = np.diff(pts, axis=1)
    rect[1] = pts[np.argmin(diff)]
    rect[3] = pts[np.argmax(diff)]

    return rect


# ==========================
# FUNÇÃO PRINCIPAL OCR
# ==========================

def read_answer_sheet(image_path, gabarito):

    image = Image.open(image_path)
    image = ImageOps.exif_transpose(image)

    img = np.array(image)
    img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)

    h, w = img.shape[:2]

    altura_max = 1000

    if h > altura_max:

        proporcao = altura_max / h
        novo_w = int(w * proporcao)

        img = cv2.resize(img, (novo_w, altura_max))

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    blurred = cv2.GaussianBlur(gray, (5,5),0)

    thresh = cv2.adaptiveThreshold(
        blurred,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV,
        51,
        11
    )

    contours,_ = cv2.findContours(
        thresh,
        cv2.RETR_LIST,
        cv2.CHAIN_APPROX_SIMPLE
    )

    # Estratégia 1: Procurar por contornos quadrados em cada canto
    h_img, w_img = img.shape[:2]
    
    # Definir regiões de busca para cada canto (10% de cada lado)
    corner_size = 0.15
    regions = {
        'tl': (0, int(w_img * corner_size), 0, int(h_img * corner_size)),
        'tr': (int(w_img * (1 - corner_size)), w_img, 0, int(h_img * corner_size)),
        'bl': (0, int(w_img * corner_size), int(h_img * (1 - corner_size)), h_img),
        'br': (int(w_img * (1 - corner_size)), w_img, int(h_img * (1 - corner_size)), h_img)
    }
    
    marcadores_finais = []
    
    for region_name, (x1, x2, y1, y2) in regions.items():
        best_contour = None
        best_area = 0
        
        for cnt in contours:
            # Calcular centróide
            M = cv2.moments(cnt)
            if M["m00"] == 0:
                continue
            
            cx = int(M["m10"] / M["m00"])
            cy = int(M["m01"] / M["m00"])
            
            # Verificar se está na região
            if not (x1 <= cx < x2 and y1 <= cy < y2):
                continue
            
            # Calcular perímetro e aproximação
            peri = cv2.arcLength(cnt, True)
            approx = cv2.approxPolyDP(cnt, 0.02 * peri, True)
            
            # Procurar por quadriláteros (4 lados)
            if len(approx) == 4:
                area = cv2.contourArea(cnt)
                
                # Muito mais flexível: aceitar qualquer tamanho razoável
                if 50 < area < 50000:
                    x, y, wb, hb = cv2.boundingRect(cnt)
                    
                    # Proporção próxima a 1 (quadrado)
                    if wb > 0 and hb > 0:
                        proporcao = wb / float(hb)
                        
                        if 0.4 < proporcao < 2.5:
                            # Preferir contornos maiores
                            if area > best_area:
                                best_area = area
                                best_contour = approx
        
        if best_contour is not None:
            marcadores_finais.append(best_contour)
    
    # Se não encontrou 4 marcadores, tentar estratégia alternativa
    if len(marcadores_finais) < 4:
        # Estratégia 2: Procurar pelos 4 maiores contornos quadrados na imagem toda
        candidatos = []
        
        for cnt in contours:
            peri = cv2.arcLength(cnt, True)
            approx = cv2.approxPolyDP(cnt, 0.02 * peri, True)
            
            if len(approx) == 4:
                area = cv2.contourArea(cnt)
                
                if 50 < area < 50000:
                    x, y, wb, hb = cv2.boundingRect(cnt)
                    
                    if wb > 0 and hb > 0:
                        proporcao = wb / float(hb)
                        
                        if 0.4 < proporcao < 2.5:
                            candidatos.append((area, approx))
        
        # Ordenar por área e pegar os 4 maiores
        candidatos.sort(key=lambda x: x[0], reverse=True)
        marcadores_finais = [c[1] for c in candidatos[:4]]
    
    if len(marcadores_finais) < 4:
        raise Exception("Marcadores não detectados")

    pts = []

    for c in marcadores_finais:

        M = cv2.moments(c)

        if M["m00"] != 0:

            pts.append([
                M["m10"]/M["m00"],
                M["m01"]/M["m00"]
            ])

    rect = order_points(np.array(pts, dtype="float32"))

    warped = cv2.warpPerspective(
        img,
        cv2.getPerspectiveTransform(
            rect,
            np.array([[0,0],[599,0],[599,899],[0,899]], dtype="float32")
        ),
        (600,900)
    )

    gray = cv2.cvtColor(warped, cv2.COLOR_BGR2GRAY)

    respostas_detectadas = []

    altura_total, largura_total = gray.shape

    top = int(altura_total * 0.11)
    bottom = int(altura_total * 0.92)
    left = int(largura_total * 0.18)
    right = int(largura_total * 0.91)

    grade = gray[top:bottom, left:right]

    # overlay agora é a folha inteira
    debug_overlay = warped.copy()

    h_grade, w_grade = grade.shape

    altura_linha = h_grade / 10.0

    posicoes_colunas = [0.235,0.370,0.505,0.640,0.775]

    raio = int(w_grade * 0.045)

    for i in range(len(gabarito)):

        alternativas = []
        centros = []

        for pos in posicoes_colunas:

            centro_x = int(w_grade * pos)
            centro_y = int(round((i + 0.39) * altura_linha))

            x1 = max(centro_x - raio,0)
            x2 = min(centro_x + raio,w_grade)

            y1 = max(centro_y - raio,0)
            y2 = min(centro_y + raio,h_grade)

            celula = grade[y1:y2, x1:x2]

            media_intensidade = np.mean(celula)

            alternativas.append(media_intensidade)
            centros.append((centro_x, centro_y))

        media = np.mean(alternativas)
        desvio = np.std(alternativas)

        limiar = media - (0.6 * desvio)

        marcadas = [
            idx for idx,valor in enumerate(alternativas)
            if valor < limiar
        ]

        if len(marcadas) == 0:

            respostas_detectadas.append("BRANCO")

        elif len(marcadas) > 1:

            respostas_detectadas.append("ANULADA")

            for idx in marcadas:
                cx, cy = centros[idx]

                cv2.circle(
                    debug_overlay,
                    (cx + left, cy + top),
                    raio,
                    (0,255,255),
                    3
                )

        else:

            idx = marcadas[0]

            respostas_detectadas.append(
                ["A","B","C","D","E"][idx]
            )

            cx, cy = centros[idx]

            cv2.circle(
                debug_overlay,
                (cx + left, cy + top),
                raio,
                (0,255,0),
                3
            )

        # número da questão
        cv2.putText(
            debug_overlay,
            str(i+1),
            (int(w_grade*0.05)+left, int((i+0.5)*altura_linha)+top),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (255,0,0),
            2
        )

    answers_dict = {}

    for i,resp in enumerate(respostas_detectadas):
        answers_dict[str(i+1)] = resp

    import base64

    _, buffer = cv2.imencode(".jpg", debug_overlay)
    debug_base64 = base64.b64encode(buffer).decode()

    return {
        "answers": answers_dict,
        "debug_image": debug_base64
    }
