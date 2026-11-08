"""Render human-review drafts using the saved-data audit, never experiment execution."""
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'outputs/one-session-review-2026-10-28'
a = json.loads((OUT / 'saved-data-audit.json').read_text(encoding='utf-8'))
primary = a['primary_comparisons']
ablation, versus_cnf = primary
o = a['matched_overhead_1s']
table = []
for r in a['larger_budget_table']:
    table.append(f"| {r['budget_seconds']:g} | {r['methods']['learned_frozen']['successes']}/250 | {r['methods']['cegis_cnf']['successes']}/250 | {r['learner_only_successes']} |")
ab = ablation['success']; cn = versus_cnf['success']
one_second = next(x for x in a['larger_budget_table'] if x['budget_seconds'] == 1.0)
full_success = one_second['methods']['forest_full_selected']['successes']
no_need_success = one_second['methods']['forest_no_need_selected']['successes']
def ci(x):
    return '[' + ', '.join(f'{v*100:+.1f}' for v in x['ci97_5']) + ']'

ar = f'''# مسودة الإجابات الثلاثة — 28 أكتوبر 2026

**للمراجعة وإعادة الصياغة بواسطة المؤلف البشري؛ ليست استنتاجات معتمدة باسمه أو توصية تقديم.**

الجلسة اقتصرت على قراءة الكود، والتحقق من الملفات، وإعادة تحليل السجلات المحفوظة. عدد التجارب الجديدة: {a['new_experiments']}. لا تدريب، ولا استدلال موديل، ولا solver، ولا توليد دوائر، ولا إعادة تشغيل فاحص. الأرشيف والنتائج القديمة لم يُعاد تحريرها.

## 1. ما الادعاء الذي تدعمه النتائج فعلًا؟

> في تنفيذنا المحدد لإصلاح دوائر Boolean اصطناعية بتعديل واحد، حسّن الترتيب المتعلم النجاح مقارنة بالقواعد البسيطة، وحسّنت حزمة السمات المشتقة من الهدف الغابة مقارنة بحذفها. لكن الفائدة لم تتحول إلى تفوق على CEGIS ذي ترميز CNF المباشر في المهل المختبرة. هذه نتيجة تخص النظام والمولد والموديل والبروتوكول المختبرين.

| المهلة بالثواني | المتعلم المجمد | CNF | حالات نجح فيها المتعلم دون CNF |
|---|---:|---:|---:|
{chr(10).join(table)}

**دليل الادعاء الأول:** `outputs/ablation-cnf-v3/raw_trials.jsonl`، مع إعادة التجميع في `outputs/one-session-review-2026-10-28/saved-data-audit.json#/larger_budget_table`. عند ثانية، فرق المتعلم ناقص CNF هو {cn['difference']*100:+.1f} نقطة مئوية، بفاصل مقترن 97.5% {ci(cn)}. أُعيد حساب الفاصل بنفس دالة التحليل المسجلة والبذرة وترتيب المقارنات، وطابق الملخص القديم بالضبط.

**دليل فائدة الحزمة:** الغابة الكاملة {full_success}/250 مقابل {no_need_success}/250 بعد حذف الحزمة؛ الفرق {ab['difference']*100:+.1f} نقطة، بفاصل 97.5% {ci(ab)} عند ثانية. المصدر: `saved-data-audit.json#/primary_comparisons/0` والسجلات نفسها.

**دليل المقارنة بالقواعد:** في fairness-v2 نجح المتعلم في {a['v2_counts']['learned']['successful_trials']}/{a['v2_counts']['learned']['trials']} محاولة، مقابل {a['v2_counts']['sample_error']['successful_trials']} لـsample_error و{a['v2_counts']['local_improvement']['successful_trials']} لـlocal_improvement. هذه تكرارات على {a['v2_counts']['learned']['distinct_circuits']} دائرة، وليست دوائر مستقلة بعدد المحاولات. المصدر: `outputs/fairness-v2/raw_trials.jsonl` و`saved-data-audit.json#/v2_counts`.

**الحدود:** v3 يضم {a['v3_trials']} محاولة على {a['v3_distinct_circuits']} دائرة، ويعيد استخدام حالات سبق الاطلاع عليها؛ ليس اختبارًا نهائيًا مستقلًا. توجد محاولة توقيت واحدة لكل دائرة/طريقة/مهلة. لا تثبت الأرقام أن SAT أفضل دائمًا أو أن التعلم بلا فائدة. كما لا تثبت فائدة فريدة لرسائل الاحتياج: `work/v3_features.py:no_need_features` لا يستقبل الهدف أصلًا؛ حذف الحزمة أزال كل السمات ذات معلومات الهدف. كذلك يستخدم CNF تقليم مخاريط المخارج المخالفة اعتمادًا على المواصفة الكاملة، بينما يرتب المتعلم جميع التعديلات القانونية باستخدام ثماني عينات. المقارنة صالحة لوصف النظامين المسجلين؛ لا تعزل أثر التعلم أو التمثيل عن التقليم والترميز وتوظيف المعلومات.

## 2. ماذا يتعلم باحث آخر غير «الموديل خسر أمام SAT»؟

**أ. جودة الاقتراح وتكلفة الوصول إليه شيئان يجب قياسهما معًا.** على {o['common_successes']} دائرة كبيرة نجح فيها الطرفان عند ثانية، تجاوز تجهيز المرشحين والسمات زمن CNF الكامل في {o['candidate_plus_features_slower_than_complete_cnf']}/{o['common_successes']}. المتوسطات المقترنة: التجهيز والسمات {o['mean_candidate_plus_feature_seconds']*1000:.3f} ms، والاستدلال {o['mean_inference_seconds']*1000:.3f} ms، ومحاولة CNF كاملة {o['mean_complete_cnf_seconds']*1000:.3f} ms. المصدر: السجلات وإعادة التحليل `saved-data-audit.json#/matched_overhead_1s`. **الحد:** هذه مراحل مرصودة على حالات نجاح مشتركة، وليست تجربة سببية تثبت أن تحسين مرحلة بعينها سيغير ترتيب الطرق.

**ب. قوة التنفيذ الرمزي تغيّر تفسير تفوق المتعلم.** عند ثانية على المجموعة نفسها: نجح Z3 في {a['larger_budget_table'][1]['methods']['cegis_z3']['successes']}/250، بينما CNF في {a['larger_budget_table'][1]['methods']['cegis_cnf']['successes']}/250، والمتعلم في {a['larger_budget_table'][1]['methods']['learned_frozen']['successes']}/250. المصدر: `saved-data-audit.json#/larger_budget_table/1`. **الحد:** هذا لا يعزل السبب في نوع solver؛ الترميز والتقليم وتنظيم البحث تختلف أيضًا. لا يصح تعميم النتيجة على كل الأنظمة العصبية أو الرمزية.

**ج. نتيجة إزالة السمات تحتاج ضبط تساوي المعلومات.** الأثر الموجب للحزمة ثابت في تجربتنا، لكن الكود يوضح أن المقارنة الحالية بين نموذج يرى معلومات الهدف في سماته وآخر لا يراها. إذن عبارة «الاحتياج ضروري» أقوى مما تسمح به البيانات. المصدر: `work/local_repair_pilot.py:local_features` و`work/v3_features.py:no_need_features` مع فرق الحزمة أعلاه. **الحد:** هذا تشخيص لمنهج هذه التجربة، وليس إثباتًا أن رسائل الاحتياج غير مفيدة.

**الحكم:** توجد دروس هندسية ومنهجية تتجاوز مجرد الخسارة وتستحق تقريرًا تقنيًا قابلًا لإعادة التدقيق. لم نجد في الأثر الحالي درسًا علميًا متميزًا ومختبرًا خارج تنفيذنا يكفي لتبرير ورقة مستقلة الآن. لا أعتبر خسارة SAT وحدها سبب الإغلاق، ولا أقدم هذا الحكم كتوقع قبول أو رفض من محرر.

## 3. ما أصغر تجربة ناقصة قد تؤكد أو تسقط الادعاء المتبقي؟

**تحديد فقط — لم تُنفّذ، ولا أوصي ببدئها تلقائيًا.** الادعاء الضيق القابل للاختبار: «تمثيل الاحتياج يحسن ترتيب الإصلاحات فوق تمثيل بديل يحصل على معلومات الهدف نفسها».

المقارنة المطلوبة واحدة: نفس الغابة ونفس بيانات التدريب والتحقق وإجراء اختيار البذرة ونفس قائمة التعديلات القانونية، بين:

- السمات الحالية: 13 محلية و8 من حزمة الاحتياج.
- ضبط مطابق: 13 محلية نفسها و8 قيم خطأ على مستوى المخارج، قيمة لكل صف من صفوف المواصفة الثمانية، تحسب بالمحاكاة الأمامية للتعديل، بلا رسائل عكسية.

يحصل الطرفان على الصفوف الثمانية نفسها ومعلومات هدفها، ونفس عدد السمات ومعلمات الغابة. تُثبت النماذج قبل عينة جديدة غير مستخدمة من نفس نطاق الأحجام. لا نستخدم نتائج v3 لاختيار معاملات تحقق مكسبًا.

المقياس الأساسي المحدد قبل التشغيل سيكون: وجود إصلاح صحيح ضمن أول 16 اقتراحًا لكل دائرة. هذا يفصل جودة الترتيب نسبيًا عن اختلاف تكلفة حساب التمثيل. تضمين جميع الحالات وحالات تعذر الإكمال، والإبلاغ عن زمن التجهيز كقياس ثانوي، وإعادة السحب على مستوى الدائرة؛ أعداد الحالات والمهلة وهامش الأهمية العملية تُثبت في بروتوكول منفصل قبل أي تنفيذ، ولن تُختار بعد النتائج.

- فاصل مقترن موجب بالكامل يدعم التفوق الضيق للتمثيل في تلك العينة.
- فاصل يقع بالكامل عند الصفر أو دونه يعارض ادعاء التفوق في ذلك الإعداد.
- فاصل يعبر الصفر يعني نتيجة غير حاسمة؛ لا يثبت التساوي ولا يبرر سلسلة تجارب إنقاذ.

**حد التجربة:** حتى فوز الاحتياج لا يثبت تفوقًا تشغيليًا على CNF ولا جدة أو أهلية نشر. مقارنة baseline مطابق المعلومات هي النقص الأقرب الذي يفسر الالتباس الموجود، وليست «تجربة أخيرة تضمن الورقة». إضافة دوائر حقيقية وحدها لا تفصل هذا الالتباس.

## القرار والتسليم

أوصي بإبقاء المسار الحالي مغلقًا كمسار مخطوط مجلة، وتوثيقه كتقرير تقني. لا تجارب جديدة ولا مشروع جديد. الكود والنتائج موجودان بالفعل في المستودع العام: https://github.com/ziademad02153/circuit-repair-research-archive . تم التحقق من كونه Public في هذه الجلسة. لم تُرسل مسودة الإجابات الجديدة أو استنتاجات باسم المؤلف إلى GitHub أو جهة نشر؛ تبقى للمراجعة وإعادة الصياغة البشرية. لا افتراض بشأن قبول arXiv أو المجلات.

أُعدت كذلك مسودة تقرير تقني بالإنجليزية في `docs/technical-report-draft-2026-10-28.md`؛ الأرقام ناتجة من نفس إعادة التحليل، ولا تستبدل السجلات القديمة أو تحولها إلى نتائج جديدة.
'''
(ROOT / 'docs/three-draft-answers-2026-10-28.ar.md').write_text(ar, encoding='utf-8')

en = f'''# Learned edit ranking versus direct-CNF CEGIS for single-edit circuit repair

**Technical report draft for author review. Unpublished; no acceptance or novelty claim.**

## Scope

This archive studies synthetic combinational two-input LUT circuits with harmful injected LUT, wire and permanent stuck-at faults. A repair is exactly one non-noop LUT replacement or legal earlier-source rewiring. No new gate, output rewiring or edit to a stuck gate is allowed. The stuck location is known. Rankers use eight sampled specification rows, while acceptance uses the complete specification. CNF also uses full-specification disagreements to restrict eligible edit locations. Costs of candidate generation, features, ranking, encoding, solving and checking are inside each method deadline; steady-state loading/warmup exclusions are documented in the registered protocol.

## Retained evidence

The v3 archive contains {a['v3_trials']:,} trials on {a['v3_distinct_circuits']} distinct circuits, ten methods and three separately executed budgets. The primary larger group contains 250 circuits. Cases were previously inspected in v2; this is a follow-up diagnostic, not an untouched final evaluation. A saved-data-only review reproduced the registered paired bootstrap intervals exactly, with zero new experiments.

| Budget (s) | Frozen ranker | Direct CNF/CEGIS | Ranker-only repaired cases |
|---|---:|---:|---:|
{chr(10).join(table)}

At one second, the ranker-minus-CNF success difference is {cn['difference']*100:+.1f} percentage points (paired 97.5% interval {ci(cn)} pp). A matched full-feature forest versus the no-need bundle variant differed by {ab['difference']*100:+.1f} pp ({ci(ab)} pp). The ablation removes all target-derived features, so it cannot distinguish backward need propagation from target conditioning generally.

Among {o['common_successes']} circuits repaired by both frozen ranker and CNF at one second, candidate generation plus feature construction alone exceeded complete CNF time in {o['candidate_plus_features_slower_than_complete_cnf']}. Their means were {o['mean_candidate_plus_feature_seconds']*1000:.3f} ms for candidates/features, {o['mean_inference_seconds']*1000:.3f} ms for inference and {o['mean_complete_cnf_seconds']*1000:.3f} ms for complete CNF. These conditional measurements do not constitute a causal intervention or a prediction for an optimized system.

Recorded wrong acceptances in v3: {a['wrong_acceptances_recorded']}. Successful trials with retained independent acceptance audits: {a['successful_trials_with_recorded_independent_audit']}. Solver-reported UNSAT cases: {a['solver_reported_unsat_distinct_cases']}, relative to the implemented one-edit encoding; independent UNSAT proof certificates were not retained. Checkers and solvers were not rerun during this review.

## Interpretation and limitations

The record supports a local systems result: target-derived learned ranking helps relative to ordinary local-feature ablation and simple rankings, but fails to outperform the stronger direct-CNF system under the tested deadlines. It illustrates why end-to-end proposal overhead, baseline implementation strength and information-matched ablations matter. It does not establish a general limitation of learning, a novel representation, or an intrinsic solver-versus-learning effect. CNF localization/encoding and the ranker's search organization differ.

Only one timing run per case/method/budget is available in v3. There is no public-family-held-out evaluation or comparison to published learned-repair systems. Repeated seeds/trials must not be counted as additional independent circuits. These limitations and the absence of a distinct validated broader claim motivate archiving as a technical report rather than escalating to a journal manuscript on the present evidence.

## Nearest unresolved control (not executed)

Compare the same forest and candidate list with current need-derived features versus a same-dimensional, target-conditioned control using forward per-row output errors on the same eight rows. Freeze training/selection before fresh cases; preregister a paired top-16-valid-repair endpoint and report runtime separately. This could test a narrow representation claim, but even a positive outcome would not establish deployment advantage over CNF or publishability. The current session authorizes no such experiment.

## Reproducibility

Original trials: `outputs/ablation-cnf-v3/raw_trials.jsonl`; protocol: `experiments/ablation-cnf-v3/protocol.json`; source: `work/`; review: `outputs/one-session-review-2026-10-28/saved-data-audit.json`.

`python tools/verify_archive.py` checks original files and recorded outcomes without experiments. `python tools/review_saved_results_20261028.py` reanalyzes saved data only and requires NumPy; it imports no circuit, model or solver code. `python tools/write_review_drafts_20261028.py` renders these drafts from that audit. The original archive manifest protects historical files; new review artifacts are separately identified.
'''
(ROOT / 'docs/technical-report-draft-2026-10-28.md').write_text(en, encoding='utf-8')
print('Wrote Arabic three-answer draft and English technical-report draft from saved-data audit.')
