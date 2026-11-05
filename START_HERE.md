# RTC-7 — точка входа для нового чата Claude

Репозиторий: https://github.com/kos200932-cmyk/rtc — **ветка `joints-structure`** (в `main` проекта нет).

Порядок чтения:
1. `STATUS_2026-10-26.md` — живая сводка проекта (обновляется, несмотря на дату в имени): принятая конфигурация руки
   J1–J7 + СЗУ, сборка в SolidWorks, расчёты, пронумерованный список решений и открытых вопросов.
2. Дальше — по ссылкам из сводки, по теме задачи:
   - манипулятор и сборка SW: `links-user/RTC-7-user-J1-J7.txt`, `links-user/RUN_SW2017_user_FULL.txt`,
     макрос `macros/BuildFromSpec.bas`, генератор `tools/gen_user_full.py`;
   - нагрузки: `robot/RTC-7-loads-user.md` (`tools/user_loads.py`); ТЗ на шарниры: `docs/TZ/RTC-7_TZ_sharniry.docx`;
   - прочность и жёсткость: `fea/*/summary.md`, `fea/stiffness/summary.md`, `fea/stiffness/reach1500.md`;
   - колёсная тележка: `platform/CART/CART.md` (модели, места сопряжения), `platform/CART/REACH.md` (досягаемость,
     сценарии, панель, карта грузоподъёмности), просмотр `platform/CART/RTC-7-cart-viewer-offline.html`.

Рабочие правила проекта:
- Модели строятся макросом из текстовых описаний `*.txt`; описания и генераторы — источник правды, .SLDPRT/.SLDASM
  в репозиторий не кладутся. Перед запуском макроса перезапускать SolidWorks.
- Система координат руки: X — ось J1 (вверх), x = 0 — базовая плоскость ОПУ. Тележки: Y вверх, X вдоль, Z поперёк.
- Расчёты в облаке: Python + OpenCascade (`pip install --break-system-packages cadquery-ocp`), CalculiX, FCL
  (`python-fcl trimesh rtree`), pyvista для картинок.
- После каждого законченного шага — коммит и push в `joints-structure`; итог дописывать в сводку (раздел «Открытые
  вопросы», новым пунктом с датой).

Текст для начала нового чата:

> Продолжаем проект RTC-7: репозиторий kos200932-cmyk/rtc, ветка joints-structure. Начни с START_HERE.md, затем
> STATUS_2026-10-26.md.
