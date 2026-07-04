const express = require('express');
const cors = require('cors');
const { createClient } = require('@supabase/supabase-js');
const { HorseRacingAPI } = require('@gikndue/hkjc-api');
const cron = require('node-cron');

const app = express();
const PORT = process.env.PORT || 3000;

app.use(cors());
app.use(express.json());

const supabaseUrl = process.env.SUPABASE_URL;
const supabaseKey = process.env.SUPABASE_SERVICE_ROLE_KEY;
const supabase = createClient(supabaseUrl, supabaseKey);

const horseAPI = new HorseRacingAPI();

// 26 个关键分钟（与 Streamlit 端一致）
const KEY_MINUTES = [
    90, 80, 70, 60, 50, 45, 40, 35, 30, 27, 24, 21,
    18, 15, 12, 10, 9, 8, 7, 6, 5, 4, 3, 2, 1, 0,
];

// 15 分钟 cron 对齐容差（分钟）
const SNAP_TOLERANCE = 8;
const MAX_COLLECT_MINUTES = Math.max(...KEY_MINUTES) + SNAP_TOLERANCE;
const MIN_COLLECT_MINUTES = -SNAP_TOLERANCE;

let lastCollectionSummary = null;

function isOverseasMeeting(meeting) {
    const venueCode = meeting.venueCode || '';
    return venueCode.startsWith('S') || venueCode === 'OS' || meeting.isOverseas === true;
}

function getOddsVenueCode(meeting) {
    const venueCode = meeting.venueCode || '';
    if (venueCode.startsWith('S')) {
        return venueCode;
    }
    return venueCode;
}

const MEETINGS_CACHE_MS = 5 * 60 * 1000;
let meetingsCache = { at: 0, data: null };

function invalidateMeetingsCache() {
    meetingsCache = { at: 0, data: null };
}

function extractRaceMetadata(raceDetails) {
    if (!raceDetails) {
        return {};
    }
    return {
        distance: raceDetails.distance || 0,
        surface:
            raceDetails.raceTrack?.description_ch ||
            raceDetails.raceTrack?.description_en ||
            raceDetails.surface ||
            '草地',
        going: raceDetails.go_ch || raceDetails.go_en || raceDetails.going || '好地',
        race_class:
            raceDetails.raceClass_ch ||
            raceDetails.raceClass_en ||
            raceDetails.raceClass ||
            '',
        postTime: raceDetails.postTime || '',
        raceTrack: raceDetails.raceTrack || null,
        raceCourse: raceDetails.raceCourse || null,
        race_course_code: raceDetails.raceCourse?.displayCode || '',
        total_runners: raceDetails.runners?.length || 0,
    };
}

async function enrichMeetings(activeMeetings, maxDays = 14) {
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    const futureLimit = new Date(today);
    futureLimit.setDate(futureLimit.getDate() + maxDays);

    const enriched = [];
    for (const meeting of activeMeetings) {
        const meetingDate = new Date(meeting.date);
        meetingDate.setHours(0, 0, 0, 0);
        if (meetingDate < today || meetingDate > futureLimit) {
            enriched.push(meeting);
            continue;
        }

        const venueCode = getOddsVenueCode(meeting);
        const races = [];
        for (const race of meeting.races || []) {
            try {
                const details = await horseAPI.getRaceWithDateAndVenueCode(
                    meeting.date,
                    venueCode,
                    race.no
                );
                const meta = extractRaceMetadata(details);
                races.push({
                    ...race,
                    ...meta,
                    distance: meta.distance || race.distance || 0,
                    postTime: meta.postTime || race.postTime || '',
                    going: meta.going,
                    surface: meta.surface,
                    race_class: meta.race_class,
                });
            } catch (err) {
                console.error(
                    `[meetings] enrich failed ${meeting.date} ${venueCode} R${race.no}: ${err.message}`
                );
                races.push(race);
            }
            await new Promise((resolve) => setTimeout(resolve, 30));
        }
        enriched.push({ ...meeting, races });
    }
    return enriched;
}

function snapToKeyMinute(rawMinutes) {
    if (rawMinutes > MAX_COLLECT_MINUTES || rawMinutes < MIN_COLLECT_MINUTES) {
        return null;
    }
    const rounded = Math.round(rawMinutes);
    let best = null;
    let bestDiff = Infinity;
    for (const km of KEY_MINUTES) {
        const diff = Math.abs(rounded - km);
        if (diff < bestDiff) {
            bestDiff = diff;
            best = km;
        }
    }
    return bestDiff <= SNAP_TOLERANCE ? best : null;
}

function parseWinPlaceOdds(oddsData) {
    const result = { WIN: {}, PLA: {} };
    if (!oddsData) {
        return result;
    }

    if (Array.isArray(oddsData)) {
        for (const item of oddsData) {
            const type = item.oddsType;
            if (type !== 'WIN' && type !== 'PLA') {
                continue;
            }
            for (const node of item.oddsNodes || []) {
                const horseNo = parseInt(node.combString, 10);
                const oddsValue = parseFloat(node.oddsValue);
                if (horseNo > 0 && oddsValue > 0) {
                    result[type][horseNo] = oddsValue;
                }
            }
        }
        return result;
    }

    for (const type of ['WIN', 'PLA']) {
        const list = oddsData[type] || [];
        for (const entry of list) {
            const horseNo = parseInt(entry.horseNo, 10);
            const oddsValue = parseFloat(entry.odds);
            if (horseNo > 0 && oddsValue > 0) {
                result[type][horseNo] = oddsValue;
            }
        }
    }
    return result;
}

async function hasOddsSnapshot(race, horseNo, oddsType, minutesBeforeRace) {
    try {
        const { data, error } = await supabase
            .from('odds_history')
            .select('id')
            .eq('race_date', race.date)
            .eq('venue', race.venue)
            .eq('race_no', race.raceNo)
            .eq('horse_no', horseNo)
            .eq('odds_type', oddsType)
            .eq('minutes_before_race', minutesBeforeRace)
            .limit(1);

        if (error) {
            return false;
        }
        return data && data.length > 0;
    } catch (err) {
        return false;
    }
}

async function saveOddsSnapshot(race, horseNo, oddsType, oddsValue, minutesBeforeRace) {
    try {
        const exists = await hasOddsSnapshot(race, horseNo, oddsType, minutesBeforeRace);
        if (exists) {
            return { saved: 0, skipped: 1 };
        }

        const { error } = await supabase.from('odds_history').insert({
            race_date: race.date,
            venue: race.venue,
            race_no: race.raceNo,
            horse_no: horseNo,
            odds_type: oddsType,
            odds_value: oddsValue,
            recorded_at: new Date().toISOString(),
            minutes_before_race: minutesBeforeRace,
        });

        if (error) {
            console.error(`保存赔率历史失败: ${error.message}`);
            return { saved: 0, skipped: 0, error: error.message };
        }

        console.log(
            `[保存] ${race.date} ${race.venue} R${race.raceNo} 马${horseNo} ${oddsType}=${oddsValue} @ T-${minutesBeforeRace}`
        );
        return { saved: 1, skipped: 0 };
    } catch (error) {
        console.error(`保存赔率历史异常: ${error.message}`);
        return { saved: 0, skipped: 0, error: error.message };
    }
}

async function getRacesNeedingOdds() {
    try {
        const meetings = await horseAPI.getActiveMeetings();
        const now = new Date();
        const racesToSync = [];

        for (const meeting of meetings) {
            const meetingDate = new Date(meeting.date);
            if ((meetingDate - now) > 24 * 60 * 60 * 1000) {
                continue;
            }

            const venueCode = getOddsVenueCode(meeting);

            for (const race of meeting.races || []) {
                const postTime = new Date(race.postTime);
                const minutesToStart = (postTime - now) / 1000 / 60;

                if (minutesToStart <= 180 && minutesToStart >= MIN_COLLECT_MINUTES) {
                    racesToSync.push({
                        date: meeting.date,
                        venue: venueCode,
                        originalVenue: meeting.venueCode,
                        raceNo: race.no,
                        postTime,
                        minutesToStart,
                        isOverseas: isOverseasMeeting(meeting),
                    });
                }
            }
        }

        return racesToSync;
    } catch (error) {
        console.error('获取赛事失败:', error);
        return [];
    }
}

async function collectOddsForRace(race) {
    const keyMinute = snapToKeyMinute(race.minutesToStart);
    if (keyMinute === null) {
        console.log(
            `[跳过] 非关键窗口: ${race.date} ${race.venue} R${race.raceNo} raw=${race.minutesToStart.toFixed(1)}min`
        );
        return {
            success: false,
            skipped: true,
            reason: 'outside_key_window',
            rawMinutes: Math.round(race.minutesToStart * 10) / 10,
            race: `${race.date} ${race.venue} R${race.raceNo}`,
        };
    }

    console.log(
        `[采集] ${race.date} ${race.venue} R${race.raceNo} raw=${race.minutesToStart.toFixed(1)}min -> key=T-${keyMinute}`
    );

    try {
        const oddsData = await horseAPI.getRaceOddsWithDateAndVenueCode(
            race.date,
            race.venue,
            race.raceNo,
            ['WIN', 'PLA']
        );

        if (!oddsData) {
            return {
                success: false,
                skipped: false,
                error: 'no_odds_data',
                keyMinute,
                race: `${race.date} ${race.venue} R${race.raceNo}`,
            };
        }

        const raceDetails = await horseAPI.getRaceWithDateAndVenueCode(
            race.date,
            race.venue,
            race.raceNo
        );
        const runners = raceDetails?.runners || [];
        const parsed = parseWinPlaceOdds(oddsData);

        let savedCount = 0;
        let skippedCount = 0;
        const errors = [];

        for (const runner of runners) {
            const horseNo = parseInt(runner.no, 10);
            if (!horseNo) {
                continue;
            }

            if (parsed.WIN[horseNo]) {
                const res = await saveOddsSnapshot(
                    race,
                    horseNo,
                    'WIN',
                    parsed.WIN[horseNo],
                    keyMinute
                );
                savedCount += res.saved || 0;
                skippedCount += res.skipped || 0;
                if (res.error) {
                    errors.push(res.error);
                }
            }

            if (parsed.PLA[horseNo]) {
                const res = await saveOddsSnapshot(
                    race,
                    horseNo,
                    'PLA',
                    parsed.PLA[horseNo],
                    keyMinute
                );
                savedCount += res.saved || 0;
                skippedCount += res.skipped || 0;
                if (res.error) {
                    errors.push(res.error);
                }
            }
        }

        console.log(`[采集] 完成 ${race.date} R${race.raceNo} T-${keyMinute}: saved=${savedCount}, skipped=${skippedCount}`);

        return {
            success: true,
            race: `${race.date} ${race.venue} R${race.raceNo}`,
            keyMinute,
            rawMinutes: Math.round(race.minutesToStart * 10) / 10,
            saved: savedCount,
            skipped: skippedCount,
            runners: runners.length,
            errors: errors.length ? errors.slice(0, 3) : undefined,
        };
    } catch (error) {
        console.error(`[采集] 失败: ${error.message}`);
        return {
            success: false,
            error: error.message,
            race: `${race.date} ${race.venue} R${race.raceNo}`,
            keyMinute,
        };
    }
}

async function logCollectionRun(summary) {
    lastCollectionSummary = summary;
    try {
        const { error } = await supabase.from('odds_collection_log').insert({
            run_at: summary.startedAt,
            source: summary.source,
            races_checked: summary.racesChecked,
            races_collected: summary.racesCollected,
            races_skipped: summary.racesSkipped,
            rows_saved: summary.rowsSaved,
            rows_skipped: summary.rowsSkipped,
            duration_ms: summary.durationMs,
            error_message: summary.errorMessage || null,
            details: summary.details || null,
        });
        if (error) {
            console.error('[日志] odds_collection_log 写入失败:', error.message);
        }
    } catch (err) {
        console.error('[日志] odds_collection_log 异常:', err.message);
    }
}

const DB_ROW_KEEP_LIMIT = 20000;

async function runDatabaseCleanup(keepLimit = DB_ROW_KEEP_LIMIT) {
    try {
        const { data, error } = await supabase.rpc('manual_cleanup', { p_keep: keepLimit });
        if (error) {
            console.error('[清理] manual_cleanup 失败:', error.message);
            return { success: false, error: error.message };
        }

        const tables = data?.tables || [];
        const totalDeleted = tables.reduce(
            (sum, row) => sum + (Number(row?.deleted) || 0),
            0
        );
        console.log(`[清理] 完成 keep<=${keepLimit}，共删除 ${totalDeleted} 条`);
        return { success: true, keepLimit, totalDeleted, result: data };
    } catch (err) {
        console.error('[清理] 异常:', err.message);
        return { success: false, error: err.message };
    }
}

async function runAutoOddsCollection(source = 'auto') {
    const startedAt = new Date().toISOString();
    const startTime = Date.now();
    console.log(`[采集任务] 开始 source=${source}`);

    const races = await getRacesNeedingOdds();
    const targetRaces = races.filter(
        (r) => r.minutesToStart <= MAX_COLLECT_MINUTES && r.minutesToStart >= MIN_COLLECT_MINUTES
    );

    let rowsSaved = 0;
    let rowsSkipped = 0;
    let racesCollected = 0;
    let racesSkipped = 0;
    const details = [];
    const errors = [];

    for (const race of targetRaces) {
        if (race.minutesToStart <= SNAP_TOLERANCE && race.minutesToStart >= MIN_COLLECT_MINUTES) {
            const finalRes = await updateFinalOdds(race);
            rowsSaved += finalRes.saved || 0;
            rowsSkipped += finalRes.skipped || 0;
        }
        const result = await collectOddsForRace(race);
        details.push(result);
        if (result.skipped && !result.success) {
            racesSkipped += 1;
        } else if (result.success) {
            racesCollected += 1;
            rowsSaved += result.saved || 0;
            rowsSkipped += result.skipped || 0;
        } else {
            racesSkipped += 1;
            if (result.error) {
                errors.push(`${result.race}: ${result.error}`);
            }
        }
        await new Promise((r) => setTimeout(r, 400));
    }

    const summary = {
        startedAt,
        finishedAt: new Date().toISOString(),
        source,
        racesChecked: targetRaces.length,
        racesCollected,
        racesSkipped,
        rowsSaved,
        rowsSkipped,
        durationMs: Date.now() - startTime,
        errorMessage: errors.length ? errors.slice(0, 5).join('; ') : null,
        details: details.slice(0, 30),
    };

    await logCollectionRun(summary);

    const cleanupResult = await runDatabaseCleanup(DB_ROW_KEEP_LIMIT);
    summary.cleanup = cleanupResult;

    console.log(
        `[采集任务] 完成 checked=${targetRaces.length} collected=${racesCollected} saved=${rowsSaved} skipped=${rowsSkipped}`
    );
    return summary;
}

async function syncSingleRaceToSupabase(date, venue, raceNo, isOverseas = false) {
    console.log(`[同步] ${date} ${venue} 第${raceNo}场 ${isOverseas ? '(海外赛事)' : '(本地赛事)'}`);

    try {
        const raceDetails = await horseAPI.getRaceWithDateAndVenueCode(date, venue, parseInt(raceNo));

        if (!raceDetails) {
            console.log(`[同步] ${date} ${venue} 第${raceNo}场 - 未找到赛事数据`);
            return false;
        }

        let oddsData = null;
        try {
            oddsData = await horseAPI.getRaceOddsWithDateAndVenueCode(date, venue, parseInt(raceNo), [
                'WIN',
                'PLA',
                'QIN',
            ]);
        } catch (oddsErr) {
            console.error(`[赔率] 获取失败: ${oddsErr.message}`);
            oddsData = null;
        }

        const parsed = parseWinPlaceOdds(oddsData);
        const meta = extractRaceMetadata(raceDetails);

        const { error: raceError } = await supabase.from('races').upsert(
            {
                race_date: date,
                venue,
                race_no: parseInt(raceNo),
                distance: meta.distance || 0,
                surface: meta.surface || '草地',
                going: meta.going || '好地',
                race_class: meta.race_class || '',
                total_runners: meta.total_runners || raceDetails.runners?.length || 0,
                race_status: isOverseas ? 'OVERSEAS' : 'RUNNERS',
                is_overseas: isOverseas,
                updated_at: new Date().toISOString(),
            },
            { onConflict: 'race_date,venue,race_no' }
        );

        if (raceError) {
            console.error('保存赛事失败:', raceError);
        }

        const runners = raceDetails.runners || [];
        const raceCtx = { date, venue, raceNo: parseInt(raceNo) };

        for (const runner of runners) {
            const horseId = (runner.horse && runner.horse.id) || runner.id || runner.horseId || '';
            const horseName = runner.name_en || runner.horseName || 'Unknown';
            const horseNo = parseInt(runner.no) || 0;
            const draw = parseInt(runner.barrierDrawNumber) || 0;
            const actualWeight = parseInt(runner.handicapWeight) || 0;
            const rating = parseInt(runner.internationalRating) || 0;

            let jockeyName = '';
            if (runner.jockey) {
                jockeyName = runner.jockey.name_ch || runner.jockey.name_en || '';
            }

            const horseNameZh = runner.name_ch || '';
            const winOdds = parsed.WIN[horseNo] || null;
            const placeOdds = parsed.PLA[horseNo] || null;

            if (horseId) {
                await supabase.from('horses').upsert(
                    {
                        hkjc_id: horseId,
                        name_en: horseName,
                        name_zh: horseNameZh,
                    },
                    { onConflict: 'hkjc_id' }
                );
            }

            const { error: runnerError } = await supabase.from('race_runners_clean').upsert(
                {
                    race_date: date,
                    race_no: parseInt(raceNo),
                    venue,
                    horse_id: horseId,
                    horse_name: horseName,
                    horse_name_zh: horseNameZh,
                    horse_no: horseNo,
                    draw,
                    actual_weight: actualWeight,
                    rating,
                    jockey_name: jockeyName,
                    odds_win: winOdds,
                    odds_place: placeOdds,
                },
                { onConflict: 'race_date,venue,race_no,horse_no' }
            );

            if (runnerError) {
                console.error(`保存出赛记录失败 ${horseName}:`, runnerError);
            }
        }

        console.log(`[同步完成] ${date} ${venue} 第${raceNo}场, ${runners.length} 匹马`);
        return true;
    } catch (error) {
        console.error(`同步失败 ${date} ${venue} R${raceNo}:`, error);
        return false;
    }
}

async function syncAllFutureRaces() {
    console.log(`[${new Date().toISOString()}] 开始同步未来赛事...`);
    const startTime = Date.now();

    try {
        const activeMeetings = await horseAPI.getActiveMeetings();
        const now = new Date();
        const futureMeetings = activeMeetings.filter((meeting) => new Date(meeting.date) >= now);

        let totalSyncedRaces = 0;
        let totalFailedRaces = 0;

        for (const meeting of futureMeetings) {
            const isOverseas = isOverseasMeeting(meeting);
            const venueCode = getOddsVenueCode(meeting);

            for (const race of meeting.races || []) {
                const success = await syncSingleRaceToSupabase(meeting.date, venueCode, race.no, isOverseas);
                if (success) {
                    totalSyncedRaces += 1;
                } else {
                    totalFailedRaces += 1;
                }
                await new Promise((resolve) => setTimeout(resolve, 500));
            }
        }

        const duration = Date.now() - startTime;
        console.log(`[同步完成] 耗时 ${duration}ms。成功 ${totalSyncedRaces} 场，失败 ${totalFailedRaces} 场。`);
    } catch (error) {
        console.error('[同步失败]', error);
    }
}

async function updateFinalOdds(race) {
    try {
        const oddsData = await horseAPI.getRaceOddsWithDateAndVenueCode(race.date, race.venue, race.raceNo, [
            'WIN',
            'PLA',
        ]);

        if (!oddsData) {
            return { saved: 0, skipped: 0 };
        }

        const raceDetails = await horseAPI.getRaceWithDateAndVenueCode(race.date, race.venue, race.raceNo);
        const runners = raceDetails?.runners || [];
        const parsed = parseWinPlaceOdds(oddsData);
        let updatedCount = 0;
        let savedCount = 0;
        let skippedCount = 0;

        for (const runner of runners) {
            const horseNo = parseInt(runner.no, 10);
            if (!horseNo) {
                continue;
            }

            const winOdds = parsed.WIN[horseNo];
            const placeOdds = parsed.PLA[horseNo];

            if (winOdds) {
                const winRes = await saveOddsSnapshot(race, horseNo, 'WIN', winOdds, 0);
                savedCount += winRes.saved || 0;
                skippedCount += winRes.skipped || 0;
            }
            if (placeOdds) {
                const plaRes = await saveOddsSnapshot(race, horseNo, 'PLA', placeOdds, 0);
                savedCount += plaRes.saved || 0;
                skippedCount += plaRes.skipped || 0;
            }

            if (winOdds) {
                const { error } = await supabase.from('race_runners_clean').upsert(
                    {
                        race_date: race.date,
                        race_no: race.raceNo,
                        venue: race.venue,
                        horse_no: horseNo,
                        horse_name: runner.name_en || '',
                        odds_win: winOdds,
                        odds_place: placeOdds || null,
                    },
                    { onConflict: 'race_date,venue,race_no,horse_no' }
                );
                if (!error) {
                    updatedCount += 1;
                }
            }
        }

        console.log(`[最终赔率] ${race.date} ${race.venue} R${race.raceNo}, 更新 ${updatedCount} 匹马 + T-0 快照`);
        return { saved: savedCount, skipped: skippedCount, updated: updatedCount };
    } catch (error) {
        console.error(`[最终赔率] 更新失败: ${error.message}`);
        return { saved: 0, skipped: 0, error: error.message };
    }
}

cron.schedule(
    '0 3 * * *',
    async () => {
        await syncAllFutureRaces();
    },
    {
        scheduled: true,
        timezone: 'Asia/Shanghai',
    }
);

cron.schedule(
    '*/15 * * * *',
    async () => {
        await runAutoOddsCollection('cron');
    },
    {
        scheduled: true,
        timezone: 'Asia/Shanghai',
    }
);

app.get('/api/health', (req, res) => {
    res.json({ status: 'ok', timestamp: new Date().toISOString() });
});

app.get('/api/meetings', async (req, res) => {
    try {
        const detailed = req.query.detailed !== '0';
        const activeMeetings = await horseAPI.getActiveMeetings();
        if (!detailed) {
            res.json({ success: true, data: activeMeetings, enriched: false });
            return;
        }

        const now = Date.now();
        if (meetingsCache.data && now - meetingsCache.at < MEETINGS_CACHE_MS) {
            res.json({ success: true, data: meetingsCache.data, enriched: true, cached: true });
            return;
        }

        const enriched = await enrichMeetings(activeMeetings);
        meetingsCache = { at: now, data: enriched };
        res.json({ success: true, data: enriched, enriched: true, cached: false });
    } catch (error) {
        console.error('获取赛马日失败:', error);
        res.status(500).json({ success: false, error: error.message });
    }
});

app.get('/api/race/details', async (req, res) => {
    const date = req.query.date;
    const venue = req.query.venue;
    const raceNo = parseInt(req.query.raceNo, 10);
    if (!date || !venue || !raceNo) {
        res.status(400).json({ success: false, error: 'date, venue, raceNo required' });
        return;
    }
    try {
        const raceDetails = await horseAPI.getRaceWithDateAndVenueCode(date, venue, raceNo);
        if (!raceDetails) {
            res.status(404).json({ success: false, error: 'race not found' });
            return;
        }
        res.json({ success: true, data: { ...extractRaceMetadata(raceDetails), raw: raceDetails } });
    } catch (error) {
        console.error('获取赛事详情失败:', error);
        res.status(500).json({ success: false, error: error.message });
    }
});

app.get('/api/collect/status', async (req, res) => {
    try {
        const { data, error } = await supabase
            .from('odds_collection_log')
            .select('*')
            .order('run_at', { ascending: false })
            .limit(1);

        if (error) {
            res.json({ success: true, lastRun: lastCollectionSummary, dbError: error.message });
            return;
        }

        res.json({
            success: true,
            lastRun: data && data.length ? data[0] : lastCollectionSummary,
            keyMinutes: KEY_MINUTES,
        });
    } catch (error) {
        res.status(500).json({ success: false, error: error.message, lastRun: lastCollectionSummary });
    }
});

app.post('/api/sync/race', async (req, res) => {
    const { date, venue, raceNo, isOverseas = false } = req.body;
    invalidateMeetingsCache();
    const success = await syncSingleRaceToSupabase(date, venue, parseInt(raceNo), isOverseas);

    if (success) {
        res.json({ success: true, message: `同步成功: ${date} ${venue} 第${raceNo}场` });
    } else {
        res.status(500).json({ success: false, error: '同步失败，请查看服务器日志。' });
    }
});

app.post('/api/sync/meeting', async (req, res) => {
    const { date, venue } = req.body;
    if (!date || !venue) {
        res.status(400).json({ success: false, error: 'date and venue required' });
        return;
    }

    invalidateMeetingsCache();
    try {
        const activeMeetings = await horseAPI.getActiveMeetings();
        const meeting = activeMeetings.find(
            (m) =>
                m.date === date &&
                (m.venueCode === venue || getOddsVenueCode(m) === venue)
        );

        if (!meeting) {
            res.status(404).json({ success: false, error: `meeting not found: ${date} ${venue}` });
            return;
        }

        const venueCode = getOddsVenueCode(meeting);
        const isOverseas = isOverseasMeeting(meeting);
        let synced = 0;
        let failed = 0;

        for (const race of meeting.races || []) {
            const ok = await syncSingleRaceToSupabase(date, venueCode, race.no, isOverseas);
            if (ok) {
                synced += 1;
            } else {
                failed += 1;
            }
            await new Promise((resolve) => setTimeout(resolve, 250));
        }

        res.json({
            success: true,
            message: `同步完成: ${date} ${venueCode}`,
            synced,
            failed,
            total: (meeting.races || []).length,
        });
    } catch (error) {
        console.error('同步赛马日失败:', error);
        res.status(500).json({ success: false, error: error.message });
    }
});

app.post('/api/sync/all', async (req, res) => {
    invalidateMeetingsCache();
    await syncAllFutureRaces();
    res.json({ success: true, message: '全量同步已触发' });
});

app.post('/api/collect/odds', async (req, res) => {
    const summary = await runAutoOddsCollection('manual');
    res.json({ success: true, summary });
});

app.post('/api/collect/auto', async (req, res) => {
    const summary = await runAutoOddsCollection('api_auto');
    res.json({ success: true, summary });
});

app.post('/api/odds/final', async (req, res) => {
    const races = await getRacesNeedingOdds();
    const targetRaces = races.filter((r) => r.minutesToStart <= 10 && r.minutesToStart >= 0);

    for (const race of targetRaces) {
        await updateFinalOdds(race);
    }

    res.json({ updated: targetRaces.length });
});

app.post('/api/cleanup', async (req, res) => {
    try {
        const keepLimit = Number(req.body?.keepLimit) || DB_ROW_KEEP_LIMIT;
        const cleanup = await runDatabaseCleanup(keepLimit);
        if (!cleanup.success) {
            res.status(500).json({ success: false, error: cleanup.error });
            return;
        }
        res.json({ success: true, ...cleanup });
    } catch (error) {
        console.error('清理失败:', error);
        res.status(500).json({ success: false, error: error.message });
    }
});

app.listen(PORT, '0.0.0.0', () => {
    console.log(`HKJC API Server running on port ${PORT}`);
    console.log(`赔率关键分钟: ${KEY_MINUTES.length} 点, cron 每15分钟, 容差 ${SNAP_TOLERANCE} 分钟`);
});
