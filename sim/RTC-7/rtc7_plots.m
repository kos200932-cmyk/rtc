function R = rtc7_plots(varargin)
%RTC7_PLOTS  RTC-7: графики заданных движений и возникающих моментов в шарнирах J1..J7.
%
%   rtc7_plots                      % моменты из Simscape: берёт rtc7 из рабочей области (после rtc7_build)
%                                   % или сам запускает rtc7_build
%   rtc7_plots('rerun', true)       % заново запустить моделирование Simscape
%   rtc7_plots('speed', 2)          % программа в 2 раза быстрее (моделирование запускается заново)
%   rtc7_plots('source', 'python')  % моменты из RTC-7-demo-torques-ref.csv - без Simscape (для сравнения)
%   rtc7_plots('joints', [2 3 4])   % окна только для этих шарниров (сводные графики - для всех)
%   rtc7_plots('save', false)       % не сохранять PNG и таблицу
%   R = rtc7_plots(...)             % таблица пиковых значений
%
% Для каждого шарнира - окно из 4 графиков по времени программы:
%   1) угол, град; 2) скорость, град/с; 3) ускорение, град/с^2 - заданное движение (сплайн через
%      точки демо-программы RTC-7-demo-traj.csv, то же, что подаётся на вход шарниров в модели);
%   4) момент на выходе редуктора, Н·м: Simscape (или Python), отдельно - составляющая от веса;
%      линии - номинальный и пусковой моменты редуктора (RTC-7-rated.csv).
% Сводные окна: моменты всех шарниров в % от пускового; пиковый момент (% пускового) и
% среднеквадратичный (% номинального) по шарнирам. Таблица: plots/rtc7_peaks.csv, картинки: plots/*.png.
% НЕ учтено в моделях: инерция роторов двигателей через редуктор, трение, кабели.

p = inputParser;
p.addParameter('source', 'simscape');
p.addParameter('rerun', false);
p.addParameter('speed', 1.0);
p.addParameter('joints', 1:7);
p.addParameter('save', true);
p.parse(varargin{:});
o = p.Results;
here = fileparts(mfilename('fullpath'));
src = lower(o.source);

% ---- заданное движение: тот же сплайн, что в rtc7_build (interp1 'spline' = spline, not-a-knot)
D = readmatrix(fullfile(here, 'RTC-7-demo-traj.csv'));
t = D(:, 1) / o.speed;
pp = spline(t.', D(:, 2:8).');
dpp = pp_diff(pp);
ddpp = pp_diff(dpp);

% ---- моменты
ref = readmatrix(fullfile(here, 'RTC-7-demo-torques-ref.csv'));     % t, tau J1..J7, tau_grav J1..J7 (x1)
switch src
    case 'simscape'
        out = [];
        if ~o.rerun && evalin('base', 'exist(''rtc7'', ''var'')')
            out = evalin('base', 'rtc7');
            if ~isfield(out, 'speed') || abs(out.speed - o.speed) > 1e-9, out = []; end
        end
        if isempty(out)
            out = rtc7_build('speed', o.speed);
            if isempty(out)
                error('rtc7_plots:sim', ['Моделирование не выполнено (см. сообщения rtc7_build). ' ...
                      'Графики по расчёту Python: rtc7_plots(''source'', ''python'')']);
            end
        end
        ts = out.t(:);
        tau = out.tau;
        srcName = 'Simscape Multibody';
    case 'python'
        if abs(o.speed - 1) > 1e-9
            error('rtc7_plots:speed', 'Эталон Python посчитан для скорости x1 (tools/robot_dynamics.py --speed ...)');
        end
        ts = ref(:, 1);
        tau = ref(:, 2:8);
        srcName = 'Python (Pinocchio)';
    otherwise
        error('rtc7_plots:source', 'source = ''simscape'' или ''python''');
end
q = ppval(pp, ts.').';               % N x 7, рад
qd = ppval(dpp, ts.').';
qdd = ppval(ddpp, ts.').';
tg = interp1(ref(:, 1) / o.speed, ref(:, 9:15), ts, 'linear', 'extrap');   % от веса: зависит только от углов
haveRef = strcmp(src, 'simscape') && abs(o.speed - 1) < 1e-9;
if haveRef, tref = interp1(ref(:, 1), ref(:, 2:8), ts, 'linear', 'extrap'); end

Rt = readtable(fullfile(here, 'RTC-7-rated.csv'), 'TextType', 'string');
Trat = Rt.T_rated_Nm(:).';
Tss = Rt.T_startstop_Nm(:).';
drive = cellstr(Rt.drive);
tp = ts * o.speed;                    % время программы (ось графиков), с
r2d = 180 / pi;

% ---- цвета (одна палитра для всех окон)
cMain = [0.165 0.365 0.624];  cRef = [0.55 0.58 0.62];  cGrav = [0.66 0.69 0.73];
cRated = [0.36 0.40 0.44];   cSS = [0.76 0.34 0.10];

outDir = fullfile(here, 'plots');
if o.save && ~exist(outDir, 'dir'), mkdir(outDir); end

% ---- окно на каждый шарнир: угол, скорость, ускорение, момент
for k = o.joints(:).'
    f = figure('Name', sprintf('RTC-7 J%d (%s): движение и момент', k, drive{k}), 'Color', 'w', ...
               'Position', [60 + 20 * k, 40, 900, 960]);
    tl = tiledlayout(f, 4, 1, 'TileSpacing', 'compact', 'Padding', 'compact');
    title(tl, sprintf('J%d, %s: заданное движение и момент на выходе редуктора (%s), программа x%g', ...
                      k, drive{k}, srcName, o.speed));
    ax = gobjects(4, 1);
    ax(1) = nexttile(tl);
    plot(tp, q(:, k) * r2d, 'Color', cMain, 'LineWidth', 1.6);
    ylabel('угол, °'); grid on; box off
    ax(2) = nexttile(tl);
    plot(tp, qd(:, k) * r2d, 'Color', cMain, 'LineWidth', 1.6);
    ylabel('скорость, °/с'); grid on; box off
    ax(3) = nexttile(tl);
    plot(tp, qdd(:, k) * r2d, 'Color', cMain, 'LineWidth', 1.6);
    ylabel('ускорение, °/с²'); grid on; box off
    ax(4) = nexttile(tl);
    h = plot(tp, tg(:, k), '-', 'Color', cGrav, 'LineWidth', 1.4); hold on
    lg = {'от веса'};
    if haveRef
        h(end + 1) = plot(tp, tref(:, k), '--', 'Color', cRef, 'LineWidth', 1.2); %#ok<AGROW>
        lg{end + 1} = 'Python (эталон)';
    end
    h(end + 1) = plot(tp, tau(:, k), '-', 'Color', cMain, 'LineWidth', 1.8);
    lg{end + 1} = ['с ускорениями, ' srcName];
    yline([-1 1] * Trat(k), ':', 'Color', cRated, 'LineWidth', 1.1);
    yline([-1 1] * Tss(k), '--', 'Color', cSS, 'LineWidth', 1.1);
    lim = max([1.1 * Tss(k), 1.1 * max(abs(tau(:, k)))]);
    ylim([-lim lim]);
    ylabel('момент, Н·м'); grid on; box off
    legend(h, lg, 'Location', 'northwest', 'Box', 'off');
    [pk, ip] = max(abs(tau(:, k)));
    title(sprintf('пик %.0f Н·м при t = %.1f с (%.0f %% пускового %.0f); RMS %.0f Н·м (%.0f %% номинала %.0f). ' , ...
          pk, tp(ip), 100 * pk / Tss(k), Tss(k), rms_(tau(:, k)), 100 * rms_(tau(:, k)) / Trat(k), Trat(k)), ...
          'FontWeight', 'normal', 'FontSize', 9);
    xlabel('время программы, с');
    linkaxes(ax, 'x'); xlim(ax(1), [tp(1) tp(end)]);
    if o.save, save_fig(f, fullfile(outDir, sprintf('J%d_motion_torque.png', k))); end
end

% ---- сводно: моменты всех шарниров в % пускового
f = figure('Name', 'RTC-7: моменты всех шарниров', 'Color', 'w', 'Position', [120 40 900 980]);
tl = tiledlayout(f, 7, 1, 'TileSpacing', 'compact', 'Padding', 'compact');
title(tl, sprintf('RTC-7: момент в шарнирах, %% пускового момента редуктора (%s), программа x%g', srcName, o.speed));
ax = gobjects(7, 1);
for k = 1:7
    ax(k) = nexttile(tl);
    plot(tp, 100 * tg(:, k) / Tss(k), 'Color', cGrav, 'LineWidth', 1.2); hold on
    plot(tp, 100 * tau(:, k) / Tss(k), 'Color', cMain, 'LineWidth', 1.6);
    yline([-100 100], '--', 'Color', cSS);
    yline([-1 1] * 100 * Trat(k) / Tss(k), ':', 'Color', cRated);
    lim = max(110, 110 * max(abs(tau(:, k))) / Tss(k));
    ylim([-lim lim]); grid on; box off
    ylabel(sprintf('J%d, %%', k));
    if k == 1, legend({'от веса', 'с ускорениями'}, 'Location', 'northwest', 'Box', 'off', 'Orientation', 'horizontal'); end
end
xlabel('время программы, с'); linkaxes(ax, 'x'); xlim(ax(1), [tp(1) tp(end)]);
if o.save, save_fig(f, fullfile(outDir, 'all_joints_torque.png')); end

% ---- таблица пиков
n = 7;
[qmin, qmax, vmax, amax, tpk, tAt, trms, grav] = deal(zeros(n, 1));
for k = 1:n
    qmin(k) = min(q(:, k)) * r2d;  qmax(k) = max(q(:, k)) * r2d;
    vmax(k) = max(abs(qd(:, k))) * r2d;  amax(k) = max(abs(qdd(:, k))) * r2d;
    [tpk(k), ip] = max(abs(tau(:, k)));  tAt(k) = tp(ip);
    trms(k) = rms_(tau(:, k));  grav(k) = max(abs(tg(:, k)));
end
st = strings(n, 1);
for k = 1:n
    if tpk(k) > Tss(k)
        st(k) = "пик выше пускового";
    elseif trms(k) > Trat(k)
        st(k) = "RMS выше номинала";
    elseif tpk(k) > Trat(k)
        st(k) = "пик выше номинала (в пределах пускового)";
    else
        st(k) = "в пределах номинала";
    end
end
R = table(string(compose('J%d', (1:n).')), string(drive(:)), round(qmin, 1), round(qmax, 1), round(vmax), round(amax), ...
          round(grav), round(tpk), round(tAt, 1), round(trms), Trat(:), Tss(:), ...
          round(100 * tpk ./ Tss(:)), round(100 * trms ./ Trat(:)), st, ...
          'VariableNames', {'Joint', 'Drive', 'q_min_deg', 'q_max_deg', 'v_max_deg_s', 'a_max_deg_s2', ...
                            'T_grav_max_Nm', 'T_peak_Nm', 't_peak_s', 'T_rms_Nm', 'T_rated_Nm', 'T_startstop_Nm', ...
                            'peak_pct_startstop', 'rms_pct_rated', 'Status'});
fprintf('\nRTC-7, %s, программа x%g:\n', srcName, o.speed);
disp(R);

% ---- сводно: пик и RMS по шарнирам
f = figure('Name', 'RTC-7: пиковые и среднеквадратичные моменты', 'Color', 'w', 'Position', [160 120 900 420]);
b = bar(categorical(R.Joint), [R.peak_pct_startstop, R.rms_pct_rated], 'grouped'); hold on
b(1).FaceColor = cMain; b(2).FaceColor = cGrav;
yline(100, '--', 'Color', cSS, 'LineWidth', 1.1);
ylabel('%'); grid on; box off
legend({'пик, % пускового момента', 'RMS, % номинального момента', 'предел 100 %'}, 'Location', 'northwest', 'Box', 'off');
title(sprintf('RTC-7: нагрузка редукторов по демо-программе (%s, x%g)', srcName, o.speed));
if o.save
    save_fig(f, fullfile(outDir, 'peaks.png'));
    writetable(R, fullfile(outDir, 'rtc7_peaks.csv'), 'Encoding', 'UTF-8');
    fprintf('Графики и таблица: %s\n', outDir);
end
assignin('base', 'rtc7_peaks', R);
end

% =====================================================================================================
function d = pp_diff(pp)
% производная кусочного полинома (без Curve Fitting Toolbox)
[b, c, ~, k, dim] = unmkpp(pp);
if k <= 1
    d = mkpp(b, zeros(size(c, 1), 1), dim);
    return
end
d = mkpp(b, c(:, 1:k - 1) .* repmat(k - 1:-1:1, size(c, 1), 1), dim);
end

function r = rms_(x)
r = sqrt(mean(x(:) .^ 2));
end

function save_fig(f, file)
try
    exportgraphics(f, file, 'Resolution', 150);
catch
    print(f, file, '-dpng', '-r150');
end
end
