## The line under the title

Before:

> Large language models get lost on the subway. So I loaded New York's map into a computer that lives inside an LLM.

After:

> Asked to answer straight away with no map, the language model Qwen 3.5 gets lost on the subway. So I loaded New York's map into a computer that lives inside Qwen.

## The first paragraph

Before:

> Give a language model called Qwen 3.5 a few stops to follow on the New York subway, and Qwen will tell you with total confidence that you've arrived somewhere you haven't.

After:

> Give a language model called Qwen 3.5 a few stops to follow on the New York subway, with no map and no chance to work the trip out in writing first, and Qwen will tell you with total confidence that you've arrived somewhere you haven't.

## The third paragraph

Before:

> The subway map is a good test for three reasons. Stations close and reopen. There are many ways from one place to another. And models are catastrophically bad at reading the subway map without help.

After:

> The subway map is a good test for two reasons. Stations close and reopen. And there are many ways from one place to another.

## The sealed-map line in the box at the top

Before:

> On the sealed map with invented names, Qwen alone got 0 of 100,

After:

> On the sealed map with invented names, Qwen with no map got 0 of 100,

## Step 4, where reasoning is first named

Before:

> New York's subway has no Union Station. For this test I turned off Qwen's reasoning

After:

> New York's subway has no Union Station. Reasoning is Qwen's default mode, in which Qwen works a problem out in writing before answering. For this test I turned off Qwen's reasoning

## Step 14, the sentence before the chart

Before:

> The chart shows how each version did on the same 100 questions.

After:

> The chart shows how each version did on those questions.

## Step 14, the paragraph after the chart

Before:

> <p>Qwen alone got 1 right. When I pasted the relevant lines of the map into Qwen's prompt and asked Qwen to list each stop before answering, Qwen got 54 right and 36 wrong, and did not finish the other 10 within my limit of 1,024 new tokens. Qwen's reasoning stayed off for that test too, and I tried only one prompt, so Qwen might do better with another setup.</p>

After:

> <p>With no map and reasoning off, Qwen got 1 of the 100 questions right and 88 wrong, and my limit of 40 new tokens cut off the other 11 replies, none of which named the right station. With no map and reasoning on, my time limit reached only 7 questions. Qwen got none right and none wrong, and did not finish any of the 7 within my limit of 8,192 new tokens. Seven questions are too few to decide anything.</p><p>I then pasted the lines of the map that each question needs into Qwen's prompt. With reasoning off, I asked Qwen to list each stop before answering, and Qwen got 54 right and 36 wrong, and did not finish the other 10 within my limit of 1,024 new tokens. With reasoning on, I had time to run the first 28 of the 100 questions. Qwen got 26 right and none wrong, and did not finish the other 2 within my limit of 8,192 new tokens. With reasoning off, Qwen got 16 of those 28 right and 10 wrong, and did not finish 2. The two tests differ in more than the reasoning, and the questions at the end of this post say how.</p>

## Step 14, the ordinary tool

Before:

> <p>An ordinary tool outside the model, given the same queries, scored the same as the graph-qwenputer both times, so accuracy is not a reason to build the graph-qwenputer.</p>

After:

> <p>An ordinary tool outside the model, given the same queries, scored the same as the graph-qwenputer both times, and Qwen with the map lines and reasoning on got 26 right of the 28 questions that ran, so accuracy is not a reason to build the graph-qwenputer. The token counts were close too. On average, with reasoning on, Qwen wrote about 4,600 new tokens for each question, and the graph-qwenputer took about 5,400 tokens for each of the same 28 questions.</p>

## Step 14, the trip picker's sentence

Before:

> Orange marks show the stations Qwen named without the graph-qwenputer, and where several stops share a name, I marked the first of them.

After:

> Orange marks show the stations Qwen named with reasoning off, and where several stops share a name, I marked the first of them.

## Step 14, the trip picker's rows

Before:

> ["Qwen alone",a.alone],["Qwen, map in prompt",a.map],["With the graph-qwenputer",a.machine]

After:

> ["Qwen alone, reasoning off",a.alone],["Qwen with the map lines, reasoning off",a.map],["Qwen with the map lines, reasoning on",a.think],["With the graph-qwenputer",a.machine]

## The question about memorizing

Before:

>  Alone, Qwen got 10 of 600. With the map pasted in, I asked Qwen to list each stop before answering, and Qwen got 54 of 100 right, got 36 wrong and did not finish 10. On the simulator,

After:

>  With no map and reasoning off, Qwen got 10 of 600. On the simulator,

## A new question, after the question about memorizing

Before:

>   <details><summary>Did you change the test after seeing the results?</summary>

After:

>   <details><summary>Can Qwen do these trips without the graph-qwenputer?</summary><p>With the right lines of the map in Qwen's prompt and Qwen's reasoning on, Qwen got 26 of the first 28 two-train questions right and none wrong, and did not finish the other 2 within my limit of 8,192 new tokens. With no map and reasoning on, Qwen did not finish any of the 7 questions that my time limit reached, and 7 questions are too few to decide anything. Until 10 November this page said that models are catastrophically bad at reading the subway map. That sentence rested on a test with reasoning off, and I removed the sentence.</p><p>The test with reasoning on differs from the test with reasoning off in four ways: the reasoning, the prompt, the token limit and the way Qwen picks each token. Both tests gave Qwen the same lists of stops, for the two trains in each question. The test with reasoning on was my second attempt. In the first attempt I kept the instruction to list each stop and allowed 2,048 new tokens, and Qwen did not finish any of the 10 questions that ran. So I raised the limit to 8,192 new tokens, and I left out the instruction to list each stop, because with that instruction Qwen still used all 8,192 tokens on a practice question without answering. Qwen picked each token with some randomness, at the setting that Qwen's makers recommend for precise coding tasks, and I ran each question once. With reasoning off, Qwen always printed the most likely token. I chose the prompt and the setting on two practice questions, by whether Qwen finished and how many tokens Qwen used, and the README says where that choice was not even-handed. Qwen's makers recommend a limit of 32,768 tokens, which is four times my limit. I tested one model, with one prompt for each test, so a larger model, another prompt or a longer limit might do better.</p><p>I did not test Qwen with reasoning on for closures, new lines, long routes or the whole map in one prompt. Qwen's reasoning was off in every other test on this page.</p></details>
  <details><summary>Did you change the test after seeing the results?</summary>

## The question about changing the test

Before:

> The questions copy one template, so these tests measure copying a query through a map's names. The README lists each prediction I missed.

After:

> The questions copy one template, so these tests measure copying a query through a map's names. I also ran the test of Qwen with reasoning on twice, and the question above says what I changed. The README lists each prediction I missed.

## The question about reliability

Before:

> On the current version, with Qwen on the real model and the 11 layers on the simulator, Qwen closed the right stop 40 times out of 40

After:

> On the current version, with Qwen on the real model, Qwen's reasoning off and the 11 layers on the simulator, Qwen closed the right stop 40 times out of 40

## README, results table: Qwen alone

Before:

> | Qwen alone, no map, 600 questions | None | Stock Qwen | 10 right. Repeating the start station scores 18 |

After:

> | Qwen alone, no map, reasoning off, 600 questions | None | Stock Qwen | 10 right. Repeating the start station scores 18 |

## README, results table: two new rows under the map row

Before:

> | Qwen given the map and asked to list each stop before answering, reasoning off, 100 questions | None | Stock Qwen | 54 right, 36 wrong, 10 unfinished at 1,024 new tokens |


After:

> | Qwen given the map and asked to list each stop before answering, reasoning off, 100 questions | None | Stock Qwen | 54 right, 36 wrong, 10 unfinished at 1,024 new tokens |
| Qwen given the map and the question as written, reasoning on, one sample a question at temperature 0.6, the first 28 of the 100 questions | None | Stock Qwen | 26 right, 0 wrong, 2 unfinished at 8,192 new tokens. Reasoning off scored 16, 10 and 2 on the same 28 |
| Qwen alone, no map, the question as written, reasoning on, one sample a question at temperature 0.6, the first 7 of the 100 questions | None | Stock Qwen | 0 right, 0 wrong, 7 unfinished at 8,192 new tokens. Too few questions to decide anything |


## README: the normal tool

Before:

> **A normal tool outside the model scored the same as the machine on the 100 two-leg questions, before and after the fix.** Accuracy is no reason to build this.

After:

> **A normal tool outside the model scored the same as the machine on the 100 two-leg questions, before and after the fix.** Accuracy is no reason to build this. Stock Qwen with the map lines and reasoning on came close too, for about the same number of tokens: see "Qwen with reasoning on" below.

## README: a new paragraph after the Union Station test

Before:

> **The Union Station test.** For the test of Qwen alone, Qwen's reasoning was off, and the question asked for the station name only.


After:

> **The Union Station test.** For the test of Qwen alone, Qwen's reasoning was off, and the question asked for the station name only.

**Qwen with reasoning on.** Until 10 Nov the post said that models are catastrophically bad at reading the subway map. That sentence rested on the map test with reasoning off, and I removed it. Reasoning is Qwen's default mode, and every other test in this README has it off. I reran the chart's two Qwen baselines on stock Qwen3.5-4B with reasoning on. For the map test, the prompt held the lists of stops for the two trains in the question, in both directions (4 lists, or 6 where a line branches; 591 to 1,076 prompt tokens, about a tenth of the map's lists of stops), and the question as written, with no instruction to list each stop. I took one sample a question at the model card's setting for precise coding tasks (temperature 0.6, top-p 0.95, top-k 20, no presence penalty), with a limit of 8,192 new tokens where the card recommends 32,768. The run's 8,500 s covered the first 28 of the 100 questions in file order: 26 right, 0 wrong and 2 unfinished at the limit, against 16, 10 and 2 for the same 28 with reasoning off. In both unfinished replies Qwen's text had reached the right station when the tokens ran out, which is my reading and is in no count. Qwen wrote a mean of 4,578 new tokens a question (median 4,372), about 14 times as many as with reasoning off, and the fixed build's exam took a mean of 5,402 tokens on the same 28 questions. The seconds are not a fair comparison: on the real model the fixed build took 87 s a question, and Qwen with reasoning on took 309 s with a game using the GPU. Qwen alone with reasoning on had 4,100 s, which covered the first 7 questions: 0 right, 0 wrong and 7 unfinished. In all 7 Qwen was still reasoning at the limit, trying to recall the lines' stops, and in 6 of the 7 Qwen was repeating itself. I predicted at most 40% unfinished, and that prediction missed. By my rule, fewer than 25 questions decide nothing, so the post gives these counts and draws no bar.

**What that result can't carry.** The two map rows differ in reasoning, prompt, decoding and limit, and no run isolates one of the four. I chose the prompt and the decoding on two practice questions outside the exam, by whether Qwen finished and how many tokens Qwen used, and never by whether an answer was right. That rule wasn't even-handed: I wrote it after the list-each-stop prompt had already failed one practice run, and it set a token line for the list-each-stop prompt only. With the list-each-stop prompt Qwen used all 8,192 tokens on a practice question once, and I stopped a second run at 6,000 tokens with Qwen still reasoning, so no row shows that the list-each-stop prompt fails at the setting that ran. The practice questions use the map lines of exam questions 103 and 108, and questions 116 and 125 share those lines. Without 103 and 108 the count is 24 right of 26, and without all four it is 22 right of 24, which is under the 25 finished questions that my rule asked for. On the 18 questions that I hadn't seen with reasoning on before this run, 110 to 127, the count is 17 right, 0 wrong and 1 unfinished. 26 of 28 has an exact 95% interval of 76% to 99%, with the question as the unit and one sample each. On question 121 Qwen spent part of its 8,192 tokens on whether the map's "7 southbound" label matches the real city, so this test doesn't fully separate reading the lists from knowing New York. 12 of the 28 questions start at a name that several stops share, and Qwen was right on all 12, because the question names the train. I didn't test reasoning on with closures, new lines, long routes, the sealed maps or the whole map in one prompt. This is one model, with one prompt for each test. A first attempt with the list-each-stop prompt and a 2,048-token limit ran 10 questions before the Mac went to sleep, and Qwen finished none of them. Rows: `exam/results/after/think2/`, `exam/results/after/think2_dev/` and `exam/results/after/think/`.


## README: the driver paragraph's contrast

Before:

> where Qwen with the map gave 36 wrong; a normal tool refuses the same way.

After:

> where Qwen with the map and reasoning off gave 36 wrong; a normal tool refuses the same way.

## README: predictions that missed, a new row

Before:

> | Walkthrough: right on all 4 turns | 4 of 4 |

After:

> | Qwen given the map, reasoning on, first attempt: list-each-stop prompt, 2,048-token limit | At most 25 of 100 unfinished, and both arms finish inside their deadlines | 10 questions ran before the Mac went to sleep, and all 10 were unfinished at the limit. The one allowed revision used the plain question and 8,192 tokens: 26 right, 0 wrong, 2 unfinished of 28 |
| Qwen alone, no map, reasoning on, the revision | At most 40% unfinished | 7 of 7 unfinished at 8,192 new tokens, on the 7 questions that the time limit reached |
| Walkthrough: right on all 4 turns | 4 of 4 |

## Launch copy, X thread 5

Before:

> Alone, Qwen got 0 of 100 there.

After:

> With no map, Qwen got 0 of 100 there.

## The objections table, row 7

Before:

> No training; Qwen alone 10 of 600; map-in-prompt 54 of 100; wrong map 0 of 600

After:

> No training; Qwen alone, reasoning off, 10 of 600; wrong map 0 of 600

## The still article's line under the title

Before:

> Large language models get lost on the subway. So I loaded New York's map into a computer that lives inside an LLM.

After:

> Asked to answer straight away with no map, the language model Qwen 3.5 gets lost on the subway. So I loaded New York's map into a computer that lives inside Qwen.

