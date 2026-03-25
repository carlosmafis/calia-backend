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

    # Threshold adaptativo para detectar áreas escuras (marcadores)
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

    # Procurar por quadrados pretos (marcadores)
    quadrados = []
    
    for cnt in contours:
        peri = cv2.arcLength(cnt, True)
        approx = cv2.approxPolyDP(cnt, 0.02 * peri, True)
        
        # Deve ser um quadrilátero (4 lados)
        if len(approx) == 4:
            area = cv2.contourArea(cnt)
            
            # Área razoável para um marcador (não muito pequeno, não muito grande)
            if 500 < area < 15000:
                x, y, w_rect, h_rect = cv2.boundingRect(cnt)
                
                # Deve ser aproximadamente quadrado
                if w_rect > 0 and h_rect > 0:
                    aspect_ratio = float(w_rect) / h_rect
                    
                    # Proporção próxima a 1 (quadrado)
                    if 0.7 < aspect_ratio < 1.3:
                        # Verificar se é preto (baixa intensidade média)
                        mask = np.zeros(gray.shape, dtype=np.uint8)
                        cv2.drawContours(mask, [cnt], 0, 255, -1)
                        mean_intensity = cv2.mean(gray, mask=mask)[0]
                        
                        # Se é escuro (preto), é um marcador
                        if mean_intensity < 100:
                            quadrados.append({
                                'contour': approx,
                                'area': area,
                                'centroid': (int(x + w_rect/2), int(y + h_rect/2))
                            })
    
    # Se não encontrou quadrados, tentar com critérios mais flexíveis
    if len(quadrados) < 4:
        quadrados = []
        
        for cnt in contours:
            peri = cv2.arcLength(cnt, True)
            approx = cv2.approxPolyDP(cnt, 0.02 * peri, True)
            
            if len(approx) == 4:
                area = cv2.contourArea(cnt)
                
                # Critérios muito mais flexíveis
                if 200 < area < 30000:
                    x, y, w_rect, h_rect = cv2.boundingRect(cnt)
                    
                    if w_rect > 0 and h_rect > 0:
                        aspect_ratio = float(w_rect) / h_rect
                        
                        # Mais flexível
                        if 0.5 < aspect_ratio < 2.0:
                            quadrados.append({
                                'contour': approx,
                                'area': area,
                                'centroid': (int(x + w_rect/2), int(y + h_rect/2))
                            })
    
    if len(quadrados) < 4:
        raise Exception("Marcadores não detectados")
    
    # Ordenar por área e pegar os 4 maiores
    quadrados.sort(key=lambda x: x['area'], reverse=True)
    top_4 = quadrados[:4]
    
    # Ordenar os 4 maiores pelos cantos (tl, tr, br, bl)
    pts = np.array([q['centroid'] for q in top_4], dtype="float32")
    
    rect = order_points(pts)

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
