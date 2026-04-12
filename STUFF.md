

Okay I want to articulate some unstructured thoughts on the work ahead for the weekend, which has a few categories:
1. One is the philosophy or constitution operating instructions, a slight context refactor towards the notion of only always describing facts. This means that in order to make forward-looking statements or do synthesis, it has to be very statistically rigorously oriented towards x implies y or the mix of x and y implies z. That is the kind of context refactor.
2. The next thing is the week that was piece. This guy wants to set up a process to write a week that was piece. We have to ingest like 20 of them from all periods in time and be able to articulate the essence of what that piece looks like, including the language, the exhibits, the graphics, the distinctions between pure factual information and synthesis, as well as how what has happened is described in a timeline sense. Prism needs a good sense of a timeline, which I guess then does implicate lsag in the sense that prism does need a good timeline of what has happened each day that it should be able to receive in terms of that state of the world. That is a little bit of a state of the world upgrade which we can and will do because of the logic that exists already with respect to news summarizer and also the else one-pager. All that logic exists, which means that we can easily set up that timeline through time perspective on how the world works.


As part of that when you distill the week that was piece to its core elements and then write out that prompt and then test it and execute it, or to get that all working 

And then on top of that are basically scheduled processes. Similar to how each user has a file cabinet and memories and all of that, each user should also have scheduled processes that are like structured JSONs that contain:
- metadata
- a prompt obviously
- a set of tool calls or guidance on the set of tool calls
- guidance on the number of sequential LLM calls
- breaking it up, all of that should be structured in that JSON


and then just have a job running an entry point that, whenever the time passes, executes that LLM call. I think that the way that this should generally conclude is that the final thing is a send email MCP tool call, which then kicks off the ability for the user to continue interacting with that PC through email and using the session folder, which is just a generic ephemeral sessions folder where the artifacts for that session live. 

So we need to set up that entire scheduled processes system to live as an additional JSON inside each user's folder in the S3. We need to test it out. We have to make the week that was piece be a version of that. We have to basically build out a few working examples, including the fed , equity earnings, etc

Okay a couple more things that I want to articulate in terms of the scheduling of processes, that whole workflow. Basically what needs to happen is that, right when the workflow gets kicked off, the system sends an email and then it should end with the send email MCP tool as well so we need to get that working.


